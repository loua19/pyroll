"""Contains utilities for building, loading/saving, and processing datasets of 
piano-roll objects."""

import json
import logging
import mido
from typing import Callable, Optional
from pathlib import Path
from progress.bar import Bar


from . import pianoroll
from .pianoroll import PianoRoll
from .mutopia import parse_rdf_metadata, filter_instrument


class PianoRollDataset:
    """Container for datasets of piano-roll objects.

    Contains functionality for building, loading/saving, and processing
    datasets of piano-rolls.

    Args:
        train (list[PianoRoll]): List of PianoRoll objects.
        meta_data (dict): Dictionary of dataset level metadata.
    """

    def __init__(
        self,
        data: list[PianoRoll] = [],
        meta_data: dict = {},
    ):
        """Initialises dataset with piano-rolls and metadata."""
        self.data = data
        self.meta_data = meta_data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, ind: int):
        return self.data[ind]

    def split(self, split_ratio: float):
        """Creates a train-validation split according to a float.

        Args:
            split (float): Ratio to spit the train and validation sets.

        Returns:
            tuple (PianoRollDataset): Train and validation splits.
        """
        assert 0.0 < split_ratio < 1.0, "Invalid value for split"
        split_ind = round(len(self) * split_ratio)

        return PianoRollDataset[split_ind:], PianoRollDataset[:split_ind]

    def to_json(self, save_path: str):
        """Saves dataset to a .json file. Can be re-loaded using from_json.

        Args:
            save_path (str): Path to save .json file.
        """
        data_for_save = {"data": [], "meta_data": self.meta_data}
        for entry in self.data:
            data_for_save["data"].append(entry.to_dict())

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data_for_save, f)

    @classmethod
    def from_json(cls, load_path: str):
        """Loads datasets from a .json file.

        Args:
            load_path (str): path to load dataset from.

        Returns:
            PianoRollDataset: Dataset loaded from .json.
        """
        with open(load_path) as f:
            loaded_data = json.load(f)

        data = []
        meta_data = loaded_data["meta_data"]
        for entry in loaded_data["data"]:
            data.append(PianoRoll(**entry))

        return PianoRollDataset(data, meta_data)

    @classmethod
    def build(
        cls,
        dir: str,
        recur: bool,
        extension: str | list = "mid",
        parse_fn: Optional[Callable] = None,
        metadata_fn: Optional[Callable] = None,
        filter_fn: Optional[Callable] = None,
    ):
        """Inplace version of build_dataset.

        Args:
            dir (str): directory index from
            recur (bool, optional): If True, recursively search directories.
                Defaults to False.
            extension (str | list): File extensions to parse.
            parse_fn (Optional[Callable]): Optional callback to parse each
                located file. This function should take a file path as input,
                and output a PianoRoll object. By default this will use
                midi_to_pianoroll().
            metadata_fn (Optional[Callable]): Optional callback to add metadata
                to parsed PianoRoll object. This should take the file path as
                input and output a dictionary of metadata. By default this will
                be None.
            filter_fn (Optional[Callable]): Optional callback to filter
                PianoRolls from the dataset. This should take a PianoRoll as an
                input, and output True if the PianoRoll should be added to the
                dataset.

        Returns:
            PianoRollDataset: Dataset of parsed PianoRoll objects.
        """
        return build_dataset(
            dir, recur, extension, parse_fn, metadata_fn, filter_fn
        )


def build_dataset(
    dir: str,
    recur: bool,
    extension: str = "mid",
    parse_fn: Optional[Callable] = None,
    metadata_fn: Optional[Callable] = None,
    filter_fn: Optional[Callable] = None,
):
    """Builds a piano-roll dataset from a directory containing .mid files.

    Includes functionality for various callbacks, allowing you to customise
    which files to parse and how to parse them.

    Args:
        dir (str): directory index from
        recur (bool, optional): If True, recursively search directories.
            Defaults to False.
        extension (str | list): File extensions to parse.
        parse_fn (Optional[Callable]): Optional callback to parse each located
            file. This function should take a file path as input, and output a
            PianoRoll object. By default this will use midi_to_pianoroll().
        metadata_fn (Optional[Callable]): Optional callback to add metadata to
            parsed PianoRoll object. This should take the file path as input
            and output a dictionary of metadata. By default this will be None.
        filter_fn (Optional[Callable]): Optional callback to filter PianoRolls
            from the dataset. This should take a PianoRoll as an input, and
            output True if the PianoRoll should be added to the dataset.

    Returns:
        PianoRollDataset: Dataset of parsed PianoRoll objects.
    """

    def parse_midi(path):
        mid = mido.MidiFile(path)
        return pianoroll.midi_to_pianoroll(mid, 4)

    # By default parse .mid with parse_mid().
    if not parse_fn:
        assert extension == "mid", "Invalid extension with default parse_fn."
        parse_fn = parse_midi

    # Calculate number of files present
    num_files = 0
    for path in Path(dir).rglob(f"*.{extension}"):
        num_files += 1

    # Generate PianoRoll objects
    filter_num = 0
    parse_err_num = 0
    piano_rolls = []
    with Bar("Building dataset...", max=num_files) as bar:
        if recur is True:
            paths = Path(dir).rglob(f"*.{extension}")
        else:
            paths = Path(dir).glob(f"*.{extension}")

        for path in paths:
            # Parse path according to parse_fn
            try:
                piano_roll = parse_fn(path)
            except Exception:
                print("\n")
                logging.error(f"Parsing file at {path} failed.", exc_info=True)
                parse_err_num += 1
                bar.next()
                continue

            # Add metadata according to metadata_fn
            if metadata_fn is not None:
                piano_roll.add_metadata(metadata_fn(path))
            piano_roll.add_metadata({"file_name": path.name})

            # Filter according to filter_fn
            if filter_fn is None:
                piano_rolls.append(piano_roll)
            elif filter_fn is not None and filter_fn(piano_roll) is True:
                piano_rolls.append(piano_roll)
            else:
                filter_num += 1

            bar.next()

    print(
        f"Finished. Failed to parse {parse_err_num} files. Filtered {filter_num} files."
    )

    return PianoRollDataset(piano_rolls)


def test():
    pass


if __name__ == "__main__":
    test()
