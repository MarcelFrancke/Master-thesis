class Nurse:
    def __init__(self, dictionary):
        for k, v in dictionary.items():
            setattr(self, k, v)
        # self.id
        # self.contract
        # self.skils