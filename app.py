from flask import Flask, render_template
from trafficrl.training import training_bp

app = Flask(__name__)
app.register_blueprint(training_bp)


@app.get("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
