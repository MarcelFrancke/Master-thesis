import json
from elements.Contract import Contract
from elements.Nurse import Nurse
#import pandas as pd
from elements.Shift import Shift
from ortools.sat.python import cp_model


if __name__ == '__main__':
    contracts = []
    nurses = []
    shiftTypes = []
    shiftRepr = ['O', 'E', 'L', 'N']
    weekDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    model = cp_model.CpModel()

    with open('resources/datasets/n005w4/Sc-n005w4.json') as file:
        scenarioDict = json.load(file)
    with open('resources/datasets/n005w4/H0-n005w4-0.json') as file:
        historyDict = json.load(file)
    with open('resources/datasets/n005w4/WD-n005w4-1.json') as file:
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

all_nurses = range(len(nurses))
all_working_shifts = range(len(shiftTypes))
all_shifts = range(len(shiftTypes) + 1)
all_days = range(len(weekDays))
all_skills = range(len(skills))

def create_forbidden_succession(scData):
    forbidden_array_str = []
    forbidden_array_int = []
    for i in range(len(scData['forbiddenShiftTypeSuccessions'])):
        if not scData['forbiddenShiftTypeSuccessions'][i]['succeedingShiftTypes']:
            pass
        else:
            if scData['forbiddenShiftTypeSuccessions'][i]['precedingShiftType'] == 'Early' or 'Late' or 'Night':
                for j in range(len(scData['forbiddenShiftTypeSuccessions'][i]['succeedingShiftTypes'])):
                    forbidden_array_str.append((scData['forbiddenShiftTypeSuccessions'][i]['precedingShiftType'],
                                            scData['forbiddenShiftTypeSuccessions'][i]['succeedingShiftTypes'][j],
                                            0))
    for tuple in forbidden_array_str:
        temp = list(map(lambda x: 1 if x=='Early' else x,tuple))
        temp1 = list(map(lambda x: 2 if x=='Late' else x,temp))
        temp2 = list(map(lambda x: 3 if x=='Night' else x,temp1))
        forbidden_array_int.append(temp2)

        #res = [item.replace('Early', 1) for item in forbidden_array[i]]

    return forbidden_array_int

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
                elif wData['requirements'][j]['shiftType'] == 'Night':
                    head_night += req['minimum']
                else:
                    pass
            else:
                req = wData['requirements'][j]['requirementOn'+ wDays[i]]
                if wData['requirements'][j]['shiftType'] == 'Early':
                    nurse_early += req['minimum']
                elif wData['requirements'][j]['shiftType'] == 'Late':
                    nurse_late += req['minimum']
                elif wData['requirements'][j]['shiftType'] == 'Night':
                    nurse_night += req['minimum']
                else:
                    pass
        headnurse_demand.append((head_early, head_late, head_night))
        nurse_demand.append((nurse_early, nurse_late, nurse_night))
        demand.append((head_early + nurse_early, head_late + nurse_late, head_night + nurse_night))

    return headnurse_demand, nurse_demand, demand

def find_indices(lst, condition):
    return [i for i, elem in enumerate(lst) if condition(elem)]

weekly_demand = create_weekly_demand(weekDict, weekDays)
forbidden_shift_succession = create_forbidden_succession(scenarioDict)

obj_int_vars = []
obj_int_coeffs = []

# Creates shift variables.
shifts = {}
for n in all_nurses:
    for d in all_days:
        for s in all_shifts:
            shifts[(n, d, s)] = model.NewBoolVar('shift_n%id%is%i' % (n, d, s))

# H1: Exactly one shift per day.
for n in all_nurses:
    for d in all_days:
        model.AddExactlyOne((shifts[n, d, s] for s in all_shifts))

# H2 H4: Each shift is assigned to min requirements of nurses depending on their skills.
for s in range(1, len(shiftTypes) + 1):
    for d in all_days:
        for f in range(len(skills)):
            works = [shifts[n, d, s] for n in find_indices(nurses, lambda n: skills[f] in n.skills)]
            min_demand = weekly_demand[f][d][s - 1]
            worked = model.NewIntVar(min_demand, len(find_indices(nurses, lambda n: skills[f] in n.skills)), '')
            model.Add(worked == sum(works))
            name = 'excess_demand(shift=%i, week=%i, day=%i)' % (s, 1, d)
            excess = model.NewIntVar(0, len(find_indices(nurses, lambda n: skills[f] in n.skills)) - min_demand,
                                     name)
            model.Add(excess == worked - min_demand)
            obj_int_vars.append(excess)
            obj_int_coeffs.append(30)



# H3: Forbidden shift successions
for previous_shift, next_shift, cost in forbidden_shift_succession:
    for n in all_nurses:
        for d in range((len(all_days) - 1)):
            transition = [shifts[n, d, previous_shift].Not(), shifts[n, d + 1, next_shift].Not()]
            model.AddBoolOr(transition)


model.Minimize(sum(obj_int_vars[i] * obj_int_coeffs[i] for i in range(len(obj_int_vars))))

# Solve the model.
solver = cp_model.CpSolver()
solution_printer = cp_model.ObjectiveSolutionPrinter()
status = solver.Solve(model, solution_printer)

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print()
    header = '          '
    for w in range(1):
        header += 'M T W T F S S '
    print(header)
    for n in all_nurses:
        schedule = ''
        for d in all_days:
            for s in all_shifts:
                if solver.BooleanValue(shifts[n, d, s]):
                    schedule += shiftRepr[s] + ' '
        print('nurse %i: %s' % (n, schedule))


print('\nStatistics')
print('  - status          : %s' % solver.StatusName(status))
print('  - conflicts      : %i' % solver.NumConflicts())
print('  - branches       : %i' % solver.NumBranches())
print('  - wall time      : %f s' % solver.WallTime())
print('  - solutions found: %i' % solution_printer.solution_count())


#df = pd.DataFrame(scenarioDict['nurses'])
#pd.set_option("max_colwidth", 40)
#print(df)
