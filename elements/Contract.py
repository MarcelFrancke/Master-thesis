class Contract:
    def __init__(self, dictionary):
        for k, v in dictionary.items():
            setattr(self, k, v)
        # self.id
        # self.minimumNumberOfAssignments
        # self.maximumNumberOfAssignments
        # self.minimumNumberOfConsecutiveWorkingDays
        # self.maximumNumberOfConsecutiveWorkingDays
        # self.minimumNumberOfConsecutiveDaysOff
        # self.maximumNumberOfConsecutiveDaysOff
        # self.maximumNumberOfWorkingWeekends
        # self.completeWeekends

