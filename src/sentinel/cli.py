import typer
from sentinel.hooks import install

app = typer.Typer(help="Sentinel Linux: Predict, Protect, Recover")

@app.command()
def predict():
    """For simulating upcoming updates and kernel panics"""
    print("Sentinel Predict: Scanning for update collisions...")

@app.command()
def diagnose():
    """To analyze system logs and suggest fixes"""
    print("Sentinel Diagnose: Analyzing system logs...")

@app.command()
def install_hooks():
    """
    Install package manager hooks to run sentinel automatically (Requires Root).
    """
    install()

if __name__=="__main__":
    app()
