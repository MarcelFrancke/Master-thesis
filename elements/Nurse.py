class Nurse:
    """ Class for generic creation of nurses"""
    def __init__(self, dictionary):
        for k, v in dictionary.items():
            setattr(self, k, v)
        # self.id
        # self.contract
        # self.skils