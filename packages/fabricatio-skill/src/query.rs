//! Keyword search over the library: which fields a term is matched against, and how
//! candidates are weighted and ranked.

use rayon::prelude::*;

use crate::skill::Skill;

/// A searchable field of a [`Skill`], checked for every query term.
#[derive(Clone, Copy)]
enum SkillField {
    /// Skill name (strongest signal).
    Name,
    /// Skill tags.
    Tags,
    /// Skill description.
    Description,
    /// Skill body (weakest signal, opt-in).
    Content,
}

impl SkillField {
    /// Fields matched against each term, strongest signal first.
    const ALL: [Self; 4] = [Self::Name, Self::Tags, Self::Description, Self::Content];

    /// Score added when a term matches this field.
    fn weight(self) -> usize {
        match self {
            Self::Name => 10,
            Self::Tags => 5,
            Self::Description => 3,
            Self::Content => 1,
        }
    }
}

/// A candidate skill prepared for matching: every searchable field lowercased once.
struct SearchableSkill {
    skill: Skill,
    name: String,
    description: String,
    tags: Vec<String>,
    /// Lowercased body; `None` while content search is disabled.
    content: Option<String>,
}

impl SearchableSkill {
    /// Lowercase the searchable fields; the body only when `in_content`.
    fn new(skill: Skill, in_content: bool) -> Self {
        Self {
            name: skill.name.to_lowercase(),
            description: skill.description.to_lowercase(),
            tags: skill.tags.iter().map(|tag| tag.to_lowercase()).collect(),
            content: in_content.then(|| skill.content.to_lowercase()),
            skill,
        }
    }

    /// Whether the lowercased `term` occurs in `field`.
    fn matches(&self, field: SkillField, term: &str) -> bool {
        match field {
            SkillField::Name => self.name.contains(term),
            SkillField::Tags => self.tags.iter().any(|tag| tag.contains(term)),
            SkillField::Description => self.description.contains(term),
            SkillField::Content => self
                .content
                .as_ref()
                .is_some_and(|body| body.contains(term)),
        }
    }
}

/// A parsed keyword query, scored against candidate skills.
pub(crate) struct SkillQuery {
    /// Lowercased whitespace-separated terms; an empty query matches everything.
    terms: Vec<String>,
    /// Whether [`SkillField::Content`] participates in matching.
    in_content: bool,
}

impl SkillQuery {
    /// Split `query` into lowercased terms.
    pub(crate) fn parse(query: &str, in_content: bool) -> Self {
        Self {
            terms: query
                .to_lowercase()
                .split_whitespace()
                .map(str::to_owned)
                .collect(),
            in_content,
        }
    }

    /// Weighted relevance of one candidate: the summed weights of every
    /// field each term matches.
    fn score(&self, skill: &SearchableSkill) -> usize {
        self.terms
            .iter()
            .map(|term| {
                SkillField::ALL
                    .iter()
                    .filter(|field| skill.matches(**field, term))
                    .map(|field| field.weight())
                    .sum::<usize>()
            })
            .sum()
    }

    /// Score all candidates in parallel; return matches by relevance, best first.
    ///
    /// An empty query returns `skills` untouched; skills scoring zero are dropped.
    pub(crate) fn search(&self, skills: Vec<Skill>) -> Vec<Skill> {
        if self.terms.is_empty() {
            return skills;
        }
        let mut scored: Vec<(usize, Skill)> = skills
            .into_par_iter()
            .filter_map(|skill| {
                let prepared = SearchableSkill::new(skill, self.in_content);
                let score = self.score(&prepared);
                (score > 0).then_some((score, prepared.skill))
            })
            .collect();
        // Stable sort: equal scores keep their input order.
        scored.sort_by_key(|(score, _)| std::cmp::Reverse(*score));
        scored.into_iter().map(|(_, skill)| skill).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a skill from plain parts; the query tests place the term in one field each.
    fn skill(name: &str, description: &str, tags: &[&str], content: &str) -> Skill {
        Skill {
            name: name.to_string(),
            description: description.to_string(),
            tags: tags.iter().map(|tag| tag.to_string()).collect(),
            content: content.to_string(),
            path: format!("{name}.md"),
        }
    }

    #[test]
    fn skill_query_ranks_name_then_tags_then_description_then_content() {
        let skills = vec![
            skill("content_hit", "", &[], "needle in the body"),
            skill("description_hit", "needle in the description", &[], ""),
            skill("tag_hit", "", &["needle"], ""),
            skill("needle", "", &[], ""),
        ];

        let hits = SkillQuery::parse("needle", true).search(skills);
        let names: Vec<&str> = hits.iter().map(|s| s.name.as_str()).collect();

        assert_eq!(
            names,
            vec!["needle", "tag_hit", "description_hit", "content_hit"]
        );
    }

    #[test]
    fn skill_query_blank_query_returns_all_untouched() {
        let skills = vec![skill("a", "", &[], ""), skill("b", "", &[], "")];

        assert_eq!(SkillQuery::parse("   ", false).search(skills).len(), 2);
    }
}
