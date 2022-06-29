class Shift:
    """ Class for generic creation of shifts"""
    def __init__(self, dictionary):
        for k, v in dictionary.items():
            setattr(self, k, v)