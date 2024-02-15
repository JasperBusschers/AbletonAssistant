import os
import re
from copy import deepcopy

from mido import MidiFile
from openai import OpenAI

from client import AbletonOSCClient

def midifile_to_notes(midifile):
    note_ons = {}
    full_notes = []
    t = 0.0
    instrument = None
    for msg in midifile:
        if msg.type == "note_on":
            note_ons[msg.note] = deepcopy(msg)
            note_ons[msg.note].time = t
        if msg.type == "note_off":
            assert msg.note in note_ons
            prev_msg = note_ons[msg.note]
            full_notes.append(
                (
                    msg.note,
                    prev_msg.velocity,
                    prev_msg.time,
                    t - prev_msg.time + msg.time,
                )
            )
        if msg.type == "program_change":
            if instrument is None:
                print("setting instrument", msg.program)
                instrument = msg.program
            else:
                print("already set instrument", msg.program)
        t += msg.time
    t -= msg.time
    return full_notes, round(t), instrument
def get_completion(
    prompt,
        key,
    model_num=3,
    system=None,
    frequency_penalty=0.0,
    presence_penalty=0.0,
):
    if model_num == 3:
        model = "gpt-3.5-turbo"
    elif model_num == 4:
        # model = "gpt-4"
        model = "gpt-4-1106-preview"
    else:
        raise Exception("Invalid model_num")
    print("using model", model)
    messages = [{"role": "system", "content": system},
                    {"role": "user", "content": prompt}]

    client = OpenAI(api_key=key)

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
    )

    return completion

def extract_message(message):
    match = re.search(r"```abc(.*?)```", message, flags=re.DOTALL | re.M)
    print(match)
    if match:
        message = match.group(1)
    else:
        print("no match so using whole string")
    message = "\n".join([x for x in message.split("\n") if x.strip() != ""])

    pattern = r'"([^"]*)"'  # Match anything inside double quotes
    message = re.sub(
        pattern, lambda x: '"' + re.sub(r",+", "", x.group(1)) + '"', message
    )

    return message

def parse_file(filename):
    # /opt/homebrew/bin/abc2midi
    os.system(f"abc2midi.exe {filename}.abc -o {filename}.midi")


def make_midi(key,prompt, filename, DEBUG=False):
    print("START MAKE MIDI", prompt, filename)
    MODEL_NUM = 4
    SYSTEM = """System: You generate music in ABC notation, respond with notation between ```abc blocks and no other text. You are given a current representation of a track with multiple instruments and melodies and are asked to fill in one of the melodies.
        Set MIDI-instrument using: %%MIDI program {GM number} (after the V: block) for drums set %%MIDI channel 10. """

    if not DEBUG:
        print(">>>>> getting response")

        response = get_completion(
            prompt,key, system=SYSTEM, model_num=MODEL_NUM, frequency_penalty=0.3
        )
        print(">>>>> raw response")
        print(response)

        message = response.choices[0].message.content

    message = extract_message(message)
    print(message)
    with open(f"{filename}.abc", "w") as f:
        f.write(message)
    parse_file(filename)
def midi_note_to_abc_pitch(midi_note):
    note_names = ['C', '^C', 'D', '^D', 'E', 'F', '^F', 'G', '^G', 'A', '^A', 'B']
    octave = (midi_note // 12) - 1
    name = note_names[midi_note % 12]
    if octave < 5:
        name = name.lower() + ("," * (5 - octave - 1))
    elif octave > 5:
        name = name + ("'" * (octave - 5))
    else:
        name = name.lower()
    return name

def duration_to_abc_length(duration):
    if duration == 0.25:
        return "/4"  # Sixteenth note
    elif duration == 0.5:
        return "/2"  # Eighth note
    elif duration == 0.75:
        return "3/4"  # Dotted eighth note
    elif duration == 1.0:
        return "1"  # Quarter note
    elif duration == 1.5:
        return "3/2"  # Dotted quarter note
    elif duration == 2.0:
        return "2"  # Half note
    elif duration == 3.0:
        return "3"  # Dotted half note
    elif duration >= 4.0:
        return str(int(duration // 4))  # Whole note and multiples
    else:
        return ""  # Default to quarter note if duration is unexpected
def melody_to_abc(melody, title="Melody Example", meter="4/4", default_length="1/8", key="Emin"):
    """
    Converts a melody string to ABC notation format.

    Parameters:
    - melody: A string representing the melody in a simplified format.
    - title: The title of the piece.
    - meter: The time signature of the piece.
    - default_length: The default note length.
    - key: The key of the piece.

    Returns:
    - A string containing the melody in ABC notation format.
    """
    # Replace the simplified note lengths with ABC notation equivalents
    melody_abc = melody.replace("1", "8").replace("/2", "2")  # Adjust note lengths

    # Format the ABC notation header
    header = f"X:1\nT:{title}\nM:{meter}\nL:{default_length}\nK:{key}\n"

    # Combine the header and the formatted melody
    abc_notation = header + "|: " + melody_abc + ":|"

    # Remove extra spaces and format for ABC notation
    abc_notation = abc_notation.replace(" ", "")

    return abc_notation
def notes_to_abc(notes):
    abc_notes = ""
    try:
        for i in range(0, len(notes), 5):
            midi_note, start, duration, velocity, _ = notes[i:i+5]
            abc_pitch = midi_note_to_abc_pitch(midi_note)
            abc_length = duration_to_abc_length(duration)
            abc_notes += abc_pitch + abc_length + " "
        return abc_notes
    except:
        return ""
class API():
    def __init__(self, IP="127.0.0.1", PORT=11000):
        # Initialize Ableton OSC client
        self.client = AbletonOSCClient(IP, PORT)
        self.tracks_clips_info = {}  # Internal variable to store tracks and their clips
        self.tracks=[]
    def get_tracks(self):
        # Query for the names of all tracks
        return self.client.query('/live/song/get/track_names', ())

    def get_clips(self):
        track_names = self.get_tracks()
        track_clips = {}
        self.tracks_clips_info = {}
        self.tracks=[]
        self.clips=[[] for _ in track_names]
        for track_index, track_name in enumerate(track_names):
            self.tracks.append(track_name)
            # Initialize an empty list for each track's clips
            track_clips[track_name] = []

            # Query for the names of clips/slots in the track
            clips_response = self.client.query('/live/track/get/clips/name', (track_index,))
            if clips_response:
                # Update the internal variable with clip names and indexes
                self.tracks_clips_info[track_name] = []
                for clip_index, clip_name in enumerate(clips_response):
                    if clip_name is not None and clip_name not in list(range(20)):
                        self.clips[track_index].append(clip_name)
                        track_clips[track_name].append(clip_name)
                        # Update the internal structure with clip name and index
                        self.tracks_clips_info[track_name].append({
                            'name': clip_name,
                            'index': clip_index-1,
                            'notes':notes_to_abc(self.get_notes(track_index,clip_index-1))
                        })

        return self.tracks_clips_info

    def remove_notes(self,x, y):
        self.client.send_message("/live/clip/remove/notes", (x, y, 0, 127, 0, 100000))

    def midifile_to_notes(midifile):
        note_ons = {}
        full_notes = []
        t = 0.0
        instrument = None
        for msg in midifile:
            if msg.type == "note_on":
                note_ons[msg.note] = deepcopy(msg)
                note_ons[msg.note].time = t
            if msg.type == "note_off":
                assert msg.note in note_ons
                prev_msg = note_ons[msg.note]
                full_notes.append(
                    (
                        msg.note,
                        prev_msg.velocity,
                        prev_msg.time,
                        t - prev_msg.time + msg.time,
                    )
                )
            if msg.type == "program_change":
                if instrument is None:
                    print("setting instrument", msg.program)
                    instrument = msg.program
                else:
                    print("already set instrument", msg.program)
            t += msg.time
        t -= msg.time
        return full_notes, round(t), instrument

    def insert_clip(self, track_index, clip_slot_index, midifilename):
            # Assuming you have a method to convert a MIDI file to note data
            midifile = MidiFile(midifilename)
            full_notes, length, instrument = midifile_to_notes(midifile)
            #x, y, name = self.client.query("/live/clip/get/name", (track_index, clip_slot_index))
            #print("Inserting midi : "+midifilename+ " into "+name)
            # Remove existing notes from the clip slot
            self.client.send_message("/live/clip/remove/notes", (track_index, clip_slot_index))

            # Create a new clip in the slot with the specified length
            self.client.send_message("/live/clip/create", (track_index, clip_slot_index, length))

            # Insert notes into the clip
            for note, velocity, start, duration in full_notes:
                self.client.send_message("/live/clip/add/notes", (
                track_index, clip_slot_index, note, start, duration, velocity, 0))  # Last param is 'mute'

            # Set loop points for the clip
            self.client.send_message("/live/clip/set/looping", (track_index, clip_slot_index, 1))  # Enable looping
            self.client.send_message("/live/clip/set/loop_start", (track_index, clip_slot_index, 0))
            self.client.send_message("/live/clip/set/loop_end", (track_index, clip_slot_index, length))
            self.client.send_message("/live/clip/set/looping",(track_index, clip_slot_index, 0))
    def get_notes(self,track_index, clip_slot_index):
        try:
            notes = self.client.query("/live/clip/get/notes", (track_index, clip_slot_index, 0, 127, 0, 100000))[2:]
            return notes
        except Exception as e:
            print("failed to get notes", e)
            return None
    def delete_notes(self,track_index, clip_slot_index):
        self.client.send_message("/live/clip/remove/notes", (track_index, clip_slot_index, 0, 127, 0, 100000))
    def play(self,track_index, clip_slot_index):
            self.client.send_message("/live/clip/fire",(track_index, clip_slot_index))

    def loop(self,track_index, clip_slot_index):
        self.client.send_message("/live/clip/set/looping", (track_index, clip_slot_index,1))

    def stop(self,track_index, clip_slot_index):
            self.client.send_message("/live/clip/stop", (track_index, clip_slot_index))

    def get_BPM(self):
            return(self.client.query("/live/song/get/tempo", ()))[0]

    def format_tracks_clips_info_as_string(self):
        formatted_string = "Tracks and Clips Information:\n"
        formatted_string += "BPM: "+str(self.get_BPM())+"\n"
        for track_name, clips in self.tracks_clips_info.items():
            if clips:
                formatted_string += f"Track: {track_name}\n"
                for clip in clips:
                    # Check if clip['notes'] is a list or tuple
                    if len(clip['notes'])>0:
                        notes_str = melody_to_abc(clip['notes'],title=track_name)
                    else:
                        notes_str = "No notes given yet"
                    formatted_string += f"  - Clip Name: {clip['name']}, Index: {clip['index']}, Notes: [{notes_str}]\n"

        return formatted_string

    def close(self):
        self.client.stop()

    def generate(self,key,prompt, track_index, clip_slot_index):
        print(self.tracks[track_index])
        print(self.clips[track_index][clip_slot_index])
        prompt = f"""Write ABC notation for track "{self.tracks[track_index]}" and clip "{self.clips[track_index][clip_slot_index]}" and this prompt:"{prompt}" \n \n"{self.format_tracks_clips_info_as_string()}"""
        make_midi(key,prompt, "gens/test")
        with open("gens/test.abc") as f:
            abc = f.read()
        import pyperclip
        pyperclip.copy(abc)
        midifile = MidiFile('gens/test.midi')
        full_notes, length, instrument = midifile_to_notes(midifile)
        self.insert_clip(track_index, clip_slot_index, 'gens/test.midi')




