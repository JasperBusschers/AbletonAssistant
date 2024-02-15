from flask import Flask, jsonify, request, render_template

from api import API


# Placeholder for the tracks data and a prompt
data_with_prompt = {
    'tracks': {
        '1-Sunrise Waves': [{'name': 'epic melody', 'index': 0, 'notes': ''}],
        '2-Backbeat Room': [
            {'name': 'house beat', 'index': 0, 'notes': '...'},
            {'name': 'smooth jazz', 'index': 1, 'notes': '...'}
        ],
        '3-Basic Guzheng': [{'name': 'nice guitar tune', 'index': 0, 'notes': ''}],
        '4-MIDI': [],
        '5-Audio': [],
        '6-Audio': []
    },
    'prompt': "Enter your creative prompt here"
}

app = Flask(__name__)
#

@app.route('/')
def home():
    a = API()
    print(a.get_clips())
    data_with_prompt['tracks']=a.get_clips()
    # Pass data_with_prompt to the template
    data_with_prompt['tracks'] = {track_name: clips for track_name, clips in data_with_prompt['tracks'].items() if clips}
    a.close()
    return render_template('tracks.html', data_with_prompt=data_with_prompt)

@app.route('/tracks', methods=['GET'])
def get_tracks():
    return jsonify(data_with_prompt)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    key = data['openAIKey']
    prompt=data['prompt']
    a = API()
    for x,y in data['selection']:
        a.delete_notes(x, y)
    for x,y in data['selection']:
        a.get_clips()
        a.generate(key,prompt, x, y)
        a.loop(x, y)
    print("Received data:", data)
    # a.delete_notes(0, 0)
    # a.delete_notes(1, 0)
    # a.delete_notes(2, 0)
    # print(a.get_clips())
    # a.generate(1, 0)
    # a.loop(1, 0)
    # print(a.get_clips())
    # a.generate(2, 0)
    # a.loop(2, 0)
    # a.generate(0, 0)
    # a.loop(0, 0)
    # Process the data as needed
    a.close()
    return jsonify({"status": "success", "message": "Data received"})


app.run(debug=True, port=80)
