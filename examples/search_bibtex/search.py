from fabricatio import BibManager

b = BibManager("Exported Items.bib")
print(b.get_cite_key("Fault Diagnosis of Wind Turbines"))
print(
    b.get_cite_key_fuzzy(
        "Fault Diagnosis of Wind Turbines"
    )
)

print(b.list_titles())
print(b.list_titles(True))
