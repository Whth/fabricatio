from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from typer import Typer

app = Typer()


@app.command()
def code():
    print("Hello, World!")    
    






if __name__ == "__main__":
    app()