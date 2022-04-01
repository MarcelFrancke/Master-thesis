import json
from elements.Contract import Contract
from elements.Nurse import Nurse
import pandas as pd
from elements.Shift import Shift
from ortools.sat.python import cp_model


if __name__ == '__main__':
    contracts = []
    nurses = []
    shiftTypes = []
    weekDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    model = cp_model.CpModel()

    with open('resources/datasets/n005w4/Sc-n005w4.json') as file:
        scenarioDict = json.load(file)
    with open('resources/datasets/n005w4/H0-n005w4-0.json') as file:
        historyDict = json.load(file)
    with open('resources/datasets/n005w4/WD-n005w4-0.json') as file:
        weekDict = json.load(file)

for i in scenarioDict['contracts']:
    contracts.append(Contract(i))

for i in scenarioDict['nurses']:
    nurses.append(Nurse(i))

for i in scenarioDict['shiftTypes']:
    shiftTypes.append(Shift(i))

for i in nurses:
    if i.contract == "FullTime":
        setattr(i, "contract", contracts[0])
    else:
        setattr(i, "contract", contracts[1])

skills = scenarioDict['skills']

print(skills)

all_nurses = range(len(nurses)-1)
all_shifts = range(len(shiftTypes)-1)
all_days = range(len(weekDays)-1)
all_skills = range(len(skills)-1)

print(all_shifts)
print(len(weekDict['requirements']))

# Creates shift variables.
shifts = {}
for n in all_nurses:
    for d in all_days:
        for s in all_shifts:
            shifts[(n, d,s)] = model.NewBoolVar('shift_n%id%is%i' % (n, d, s))

# Each shift is assigned to min requirements of nurses.
for d in all_days:
    for s in all_shifts:
        model.Add(sum(shifts[(n, d, s)] for n in all_nurses) == 1)

df = pd.DataFrame(scenarioDict['nurses'])
pd.set_option("max_colwidth", 40)
print(df)
