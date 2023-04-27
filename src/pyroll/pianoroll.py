"""Includes functions for converting between piano-roll and other formats such
as MIDI. In the future more formats will be added such as LilyPond and 
MusicXML."""

import math
import collections
import mido

# TODO:
# - Add functionality for LilyPond and MusicXML.


class PianoRoll:
    """Container for piano-roll objects, includes data and meta-data.

    Includes functionality for converting between PianoRoll and mido.MidiFile
    formats. Notes in the piano-roll take the form {"val": int, "art": str}
    where "val" indicates the midi note value, and "art" indicates articulation
    of the note ("s" and "l" for staccato and legato respectfully).

    Args:
        roll (list): Piano-roll indicating when notes are on. Defaults to [].
        meta_data (dict): Dictionary containing metadata about the piano-roll.
            This can also contain a list of midi meta-messages if applicable.
            Defaults to {"meta_events": {}}.
    """

    def __init__(self, roll: list = [], meta_data: dict = {"meta_events": {}}):
        """Initialises PianoRoll with data and metadata."""
        self.roll = roll
        self.meta_data = meta_data

    def add_metadata(self, meta_data: dict):
        """Adds (possibility overwriting) metadata to self (PianoRoll).

        Args:
            meta_data (dict): Metadata to add.
        """
        for k, v in meta_data.items():
            self.meta_data[k] = v

    def to_midi(self):
        """Inplace version of pianoroll_to_midi.

        Returns:
            mido.MidiFile: MidiFile parsed from self.
        """
        return pianoroll_to_midi(self)

    def to_dict(self):
        """Returns PianoRoll data as a dictionary.

        Returns:
            dict: PianoRoll as dictionary
        """
        return {"roll": self.roll, "meta_data": self.meta_data}

    @classmethod
    def from_midi(cls, mid: mido.MidiFile, div: int, pedal: bool = True):
        """Inplace version of midi_to_pianoroll.

        Args:
            mid (mido.MidiFile): MidiFile to be parsed.
            div (int): Amount to subdivide each beat.

        Returns:
            PianoRoll: mid as a PianoRoll object.
        """
        return midi_to_pianoroll(mid, div, pedal)

    @classmethod
    def from_seq(cls, seq: list):
        """Encodes sequence"""
        roll = []
        meta_data = {"meta_events": {}}

        chord = []
        for tok in seq:
            if isinstance(tok, int):
                chord.append(tok)
            elif tok == "<T>":
                roll.append(list(set(chord)))
                chord = []
            else:
                pass

        return PianoRoll(roll, meta_data)


def pianoroll_to_midi(piano_roll: PianoRoll):
    """Parses a PianoRoll object into a mid.MidiFile object.

    Automatically adds midi meta-messages located in meta_data["meta_events"]
    if present.

    Args:
        piano_roll (PianoRoll): piano-roll to be parsed.

    Returns:
        mido.MidiFile: resulting MidiFile.
    """

    def _turn_on(track: mido.MidiTrack, notes: list):
        """Adds all notes as note_on events to track."""
        for note in notes:
            # Turn off then on (for staccato)
            track.append(
                mido.Message(
                    "note_off", channel=0, note=note, velocity=100, time=0
                )
            )
            track.append(
                mido.Message(
                    "note_on", channel=0, note=note, velocity=100, time=0
                )
            )
            on_notes.append(note)

    def _turn_off(track: mido.MidiTrack, notes: list):
        """Adds notes as note_off events to track."""
        for note in notes:
            track.append(
                mido.Message(
                    "note_off", channel=0, note=note, velocity=100, time=0
                )
            )
            on_notes.remove(note)

    ticks_per_step = piano_roll.meta_data.get("ticks_per_step", 64)
    div = piano_roll.meta_data.get("div", 4)

    mid = mido.MidiFile(type=1)
    mid.ticks_per_beat = div * ticks_per_step

    meta_track = mido.MidiTrack()
    track = mido.MidiTrack()
    mid.tracks.append(meta_track)
    mid.tracks.append(track)

    # Add meta events to meta_track
    meta_track.append(mido.Message("program_change", program=0, time=0))
    meta_track.append(mido.MetaMessage("set_tempo", tempo=1_000_000, time=0))
    if piano_roll.meta_data["meta_events"]:
        piano_roll.meta_data["meta_events"].sort(key=lambda v: v["time"])
    prev_time = 0
    for meta_event in piano_roll.meta_data["meta_events"]:  # Will throw err
        meta_track.append(
            mido.MetaMessage(
                type=meta_event["type"],
                time=(meta_event["time"] - prev_time) * (ticks_per_step),
                **meta_event["data"],
            )
        )
        prev_time = meta_event["time"]

    # Add note events to track
    delta_t = 0
    on_notes = []
    for curr_notes in piano_roll.roll:
        turn_on_notes = [
            note["val"] for note in curr_notes if note["val"] not in on_notes
        ]
        turn_on_notes += [
            note["val"] for note in curr_notes if note["art"] == "s"
        ]
        turn_on_notes = list(set(turn_on_notes))  # Remove dupes

        turn_off_notes = [
            note_val
            for note_val in on_notes
            if note_val not in [note["val"] for note in curr_notes]
        ]

        if turn_off_notes == [] and turn_on_notes == []:
            delta_t += ticks_per_step
        else:
            ind = len(track)
            _turn_off(track, turn_off_notes)
            _turn_on(track, turn_on_notes)
            track[ind].time += delta_t
            delta_t = ticks_per_step

    track.append(mido.MetaMessage("end_of_track", time=0))

    return mid


def midi_to_pianoroll(mid: mido.MidiFile, div: int, pedal: bool = True):
    """Parses a mido.MidiFile object into a PianoRoll object.

    Args:
        mid (mido.MidiFile): Midi to be converted to piano-roll.
        div (int): Amount to subdivide each beat by during quantisation.
        pedal (bool): Whether to elongate notes when the sustain pedal is down.
            Defaults to True.

    Returns:
        PianoRoll: mid as a PianoRoll object.
    """

    def _get_metadata(mid: mido.MidiFile, ticks_per_step: int, div: int):
        """Returns list of relevant metadata and meta-events (e.g. tempo)
        present in mid. This is useful when parsing a PianoRoll object back
        into midi form. Note mid is expected to have event times in absolute
        units."""
        meta_data = {"ticks_per_step": ticks_per_step}
        meta_data["div"] = div

        meta_events = []
        for track in mid.tracks:
            for event in track:
                if event.type == "set_tempo":
                    meta_event = {}
                    meta_event["type"] = "set_tempo"
                    meta_event["time"] = event.time // ticks_per_step
                    meta_event["data"] = {"tempo": event.tempo}
                elif event.type == "key_signature":
                    meta_event = {}
                    meta_event["type"] = "key_signature"
                    meta_event["time"] = event.time // ticks_per_step
                    meta_event["data"] = {"key": event.key}
                else:
                    continue

                # Check if meta event is unique
                occurred = False
                for event in meta_events:
                    if (
                        meta_event["type"] == event["type"]
                        and meta_event["time"] == event["time"]  # noqa
                        and meta_event["data"] == event["data"]  # noqa
                    ):
                        occurred = True

                if occurred is False:
                    meta_events.append(meta_event)

        meta_data["meta_events"] = meta_events

        return meta_data

    def _get_notes(track: mido.MidiTrack):
        """Calculates and returns the notes present in the input. Inspired by
        code found at in in pretty_midi/pretty_midi.py. Note mid is expected to
        have event times in absolute units."""
        notes = []
        last_note_on = collections.defaultdict(list)

        for event in track:
            if event.is_meta is True:
                continue
            elif event.type == "note_on" and event.velocity > 0:
                last_note_on[event.note].append(event.time)
            elif event.type == "note_off" or (
                event.type == "note_on" and event.velocity == 0
            ):
                # Ignore non-existent note-ons
                if event.note in last_note_on:
                    end_tick = event.time
                    open_notes = last_note_on[event.note]

                    notes_to_close = [
                        start_tick
                        for start_tick in open_notes
                        if start_tick != end_tick
                    ]
                    notes_to_keep = [
                        start_tick
                        for start_tick in open_notes
                        if start_tick == end_tick
                    ]

                    for start_tick in notes_to_close:
                        notes.append((event.note, start_tick, end_tick))

                    if len(notes_to_close) > 0 and len(notes_to_keep) > 0:
                        # Note-on on the same tick but we already closed
                        # some previous notes -> it will continue, keep it.
                        last_note_on[event.note] = notes_to_keep
                    else:
                        # Remove the last note on for this instrument
                        del last_note_on[event.note]

        return notes

    def _get_pedal(track: mido.MidiTrack):
        """Returns periods that pedal is activated. Note mid is expected to
        have event times in absolute units."""
        pedal = []
        last_pedal_on = 0

        for event in track:
            if event.type == "control_change" and event.control == 64:
                if event.value == 127:
                    last_pedal_on = event.time
                elif event.value == 0:
                    pedal.append([last_pedal_on, event.time])
            else:
                continue

        return pedal

    ticks_per_step = int(mid.ticks_per_beat / (div))

    # Convert event_time values in mid to absolute
    for track in mid.tracks:
        curr_tick = 0
        for event in track:
            event.time += curr_tick
            curr_tick = event.time

    # Get meta_data
    meta_data = _get_metadata(mid, ticks_per_step, div)

    piano_roll = collections.defaultdict(list)
    for track in mid.tracks:
        # Get notes and pedal for each track
        mid_notes = _get_notes(track)
        mid_pedal = _get_pedal(track)

        # Compute piano_roll
        for note in mid_notes:
            start = math.ceil(note[1] / ticks_per_step)

            # If recognising pedal
            if pedal is True:
                # Calculate all relevant end times for pedal
                pedal_end_ticks = [0]
                for pedal_range in mid_pedal:
                    if pedal_range[0] < note[2] < pedal_range[1]:
                        pedal_end_ticks.append(pedal_range[1])

                end = max(
                    math.ceil(note[2] / ticks_per_step),
                    math.ceil(max(pedal_end_ticks) / ticks_per_step),
                )
            else:  # If not recognising pedal
                end = math.ceil(note[2] / ticks_per_step)

            # We use tuple form as it is both hashable and can cast into dict
            # Replace legato with staccato if present
            if (("val", note[0]), ("art", "l")) in piano_roll[start]:
                piano_roll[start].remove((("val", note[0]), ("art", "l")))
            # Add staccato
            piano_roll[start].append((("val", note[0]), ("art", "s")))

            for i in range(
                start + 1,
                end,
            ):
                # Add legato if staccato not present
                if (("val", note[0]), ("art", "s")) not in piano_roll[i]:
                    piano_roll[i].append((("val", note[0]), ("art", "l")))

    assert piano_roll, "parsed piano-roll is empty"

    # Remove duplicates and reformat
    piano_roll = [
        list(set(piano_roll.get(i, []))) for i in range(max(piano_roll.keys()))
    ]

    piano_roll = [
        [dict(note_tup) for note_tup in chord] for chord in piano_roll
    ]

    return PianoRoll(piano_roll, meta_data)


def test():
    mid = mido.MidiFile("beethoven.mid")
    p_roll = PianoRoll.from_midi(mid, 4, pedal=False)
    mid_res = p_roll.to_midi()
    mid_res.save("mid_res.mid")


if __name__ == "__main__":
    test()
