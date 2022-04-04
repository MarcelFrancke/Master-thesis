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

obj_int_vars = []
obj_int_coeffs = []

print(all_shifts)
print(weekDict['requirements'][0]['skill'])

def create_weekly_demand(wData, wDays):
    nurse_demand = []
    headnurse_demand = []
    demand = []

    for i in range(len(weekDays)):
        head_early = 0
        head_late = 0
        head_night = 0

        nurse_early = 0
        nurse_late = 0
        nurse_night = 0
        for j in range(len(wData['requirements'])):
            if wData['requirements'][j]['skill'] == 'HeadNurse':
                req = wData['requirements'][j]['requirementOn'+ wDays[i]]
                if wData['requirements'][j]['shiftType'] == 'Early':
                    head_early += req['minimum']
                elif wData['requirements'][j]['shiftType'] == 'Late':
                    head_late += req['minimum']
                else:
                    head_night += req['minimum']
            else:
                req = wData['requirements'][j]['requirementOn'+ wDays[i]]
                if wData['requirements'][j]['shiftType'] == 'Early':
                    nurse_early += req['minimum']
                elif wData['requirements'][j]['shiftType'] == 'Late':
                    nurse_late += req['minimum']
                else:
                    nurse_night += req['minimum']
        headnurse_demand.append((head_early, head_late, head_night))
        nurse_demand.append((nurse_early, nurse_late, nurse_night))
        demand.append((head_early + nurse_early, head_late + nurse_late, head_night + nurse_night))

    return headnurse_demand, nurse_demand, demand

weekly_demand = create_weekly_demand(weekDict, weekDays)
excess_cover_penalties = (2, 2, 5)

# Creates shift variables.
shifts = {}
for n in all_nurses:
    for d in all_days:
        for s in all_shifts:
            shifts[(n, d,s)] = model.NewBoolVar('shift_n%id%is%i' % (n, d, s))

# Exactly one shift per day.
for n in all_nurses:
    for d in all_days:
        model.Add((shifts[n, d, s] for s in all_shifts) == 1)

# Each shift is assigned to min requirements of nurses.
for d in all_days:
    for s in all_shifts:
        works = [shifts[n, d, s] for n in all_nurses]
        min_demand = weekly_demand[2][d][s]
        print(min_demand)
        worked = model.NewIntVar(min_demand, all_nurses, '')
        model.Add(worked == sum(works))
        over_penalty = excess_cover_penalties[s - 1]
        if over_penalty > 0:
             name = 'excess_demand(shift=%i, week=%i, day=%i)' % (s, 1,
                                                                  d)
             excess = model.NewIntVar(0, all_nurses - min_demand,
                                      name)
             model.Add(excess == worked - min_demand)
             obj_int_vars.append(excess)
             obj_int_coeffs.append(over_penalty)
        model.Add(sum(shifts[(n, d, s)] for n in all_nurses) == 1)

print(create_weekly_demand(weekDict, weekDays)[2])

df = pd.DataFrame(scenarioDict['nurses'])
pd.set_option("max_colwidth", 40)
print(df)
