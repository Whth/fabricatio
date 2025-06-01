from enum import StrEnum
from pathlib import Path
from typing import List, Self

from fabricatio_anki.rust import save_metadata
from fabricatio_core.models.generic import Named, SketchedAble, WithBriefing
from fabricatio_core.fs.curd import create_directory 
from fabricatio_anki.models.template import Template
from time import perf_counter_ns

class Constants(StrEnum):
    MEDIA = "media"
    TEMPLATES = "templates"
    MODEL = "model"
    FIELDS =  "fields"
    DECK = "deck"
    MODEL_ID= "model_id"

class Model(SketchedAble,Named):

    fields:List[str]

    templates:List[Template]



class Deck(SketchedAble,WithBriefing):

    models:List[Model]

    
    def save_to(self,path:Path|str)->Self:
        model_root= Path(path) / Constants.MODEL
        
        for m in self.models:
            create_directory(model_root/m.name)
            save_metadata(model_root, Constants.FIELDS, {Constants.MODEL_ID:perf_counter_ns(), Constants.FIELDS:m.fields})
            for t in m.templates:
                create_directory( model_root/m.name/t.name)
                
            
        
        
        return self
        
        





