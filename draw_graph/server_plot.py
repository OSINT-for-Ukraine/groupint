import json
import os.path

from dash import Dash, html, dcc, Input, Output
import dash_cytoscape as cyto
from flask import request

app = Dash(__name__, suppress_callback_exceptions=True)

json_path = os.path.abspath('draw_graph/test.json')
with open(json_path, 'rb') as file:
    elements = json.load(file)

default_stylesheet = [
    {
        'selector': 'node',
        'style': {
            'background-color': '#BFD7B5',
            'label': 'data(label)'
        }
    },
    {
        'selector': 'edge',
        'style': {
            'line-color': '#A3C4BC'
        }
    },
]

app.layout = html.Div([
    dcc.Dropdown(
        id='dropdown-update-layout',
        value='grid',
        clearable=False,
        options=[
            {'label': name.capitalize(), 'value': name}
            for name in ['grid', 'random', 'circle', 'cose', 'concentric']
        ]
    ),
    cyto.Cytoscape(
        id='cytoscape-update-layout',
        layout={'name': 'grid'},
        style={'width': '100%', 'height': '80vh', 'border': 'thin lightgrey solid', 'overflowX': 'scroll'},
        elements=elements,
        stylesheet=default_stylesheet
    ),
    html.P(id='cytoscape-update-layout-output'),
    dcc.Markdown(id='cytoscape-mouseoverNodeData-output'),
])


@app.callback(Output('cytoscape-mouseoverNodeData-output', 'children'),
              Input('cytoscape-update-layout', 'mouseoverNodeData'))
def displayTapNodeData(data):
    if data:
        data_str = ''
        for key in data:
            data_str += f'\n* **{key}**: {data.get(key, None)}'
        return "Node properties: " + data_str


@app.server.route('/update-graph', methods=['POST'])
def update_graph():
    data = request.get_json()
    with open(json_path, 'w') as file:
        json.dump(data, file)
    return {'response': 'Graph updated successfully!', 'status': 200}


@app.callback(
    Output('cytoscape-update-layout', 'layout'),
    Input('dropdown-update-layout', 'value')
)
def update_layout(layout):
    return {
        'name': layout,
        'animate': True
    }


if __name__ == '__main__':
    app.run_server(debug=True)
