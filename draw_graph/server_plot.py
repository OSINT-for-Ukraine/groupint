import json
import os
import os.path

import dash_cytoscape as cyto
from dash import Dash, Input, Output, dcc, html
from flask import request

app = Dash(__name__, suppress_callback_exceptions=True)

json_path = os.path.abspath("draw_graph/test.json")
with open(json_path, "rb") as file:
    elements = json.load(file)

_graph_elements = elements

default_stylesheet = [
    {
        "selector": "node",
        "style": {"background-color": "#BFD7B5", "label": "data(label)"},
    },
    {"selector": "edge", "style": {"line-color": "#A3C4BC"}},
]

app.layout = html.Div(
    [
        dcc.Dropdown(
            id="dropdown-update-layout",
            value="grid",
            clearable=False,
            options=[
                {"label": name.capitalize(), "value": name}
                for name in ["grid", "random", "circle", "cose", "concentric"]
            ],
        ),
        cyto.Cytoscape(
            id="cytoscape-update-layout",
            layout={"name": "grid"},
            style={
                "width": "100%",
                "height": "80vh",
                "border": "thin lightgrey solid",
                "overflowX": "scroll",
            },
            elements=elements,
            stylesheet=default_stylesheet,
        ),
        html.P(id="cytoscape-update-layout-output"),
        dcc.Markdown(id="cytoscape-mouseoverNodeData-output"),
    ]
)


@app.callback(
    Output("cytoscape-mouseoverNodeData-output", "children"),
    Input("cytoscape-update-layout", "mouseoverNodeData"),
)
def displayTapNodeData(data):
    if data:
        data_str = ""
        for key in data:
            data_str += f"\n* **{key}**: {data.get(key, None)}"
        return "Node properties: " + data_str


@app.server.route("/update-graph", methods=["POST"])
def update_graph():
    global _graph_elements
    data = request.get_json()
    _graph_elements = data
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(data, file)
    return {"response": "Graph updated successfully!", "status": 200}


@app.callback(
    Output("cytoscape-update-layout", "elements"),
    Input("graph-refresh-interval", "n_intervals"),
)
def sync_graph_elements(_n):
    return _graph_elements


@app.callback(
    Output("cytoscape-update-layout", "layout"),
    Input("dropdown-update-layout", "value"),
)
def update_layout(layout):
    return {"name": layout, "animate": True}


if __name__ == "__main__":
    port = int(os.environ.get("DASH_PORT", "8050"))
    app.run(host="0.0.0.0", port=port, debug=False)
