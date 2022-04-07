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

def create_weeks(lenght):
    planningHorizon = []
    for i in range(lenght):
        with open('resources/datasets/n005w4/WD-n005w4-' + str(i) + '.json') as file:
            planningHorizon.append(json.load(file))
    return planningHorizon

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
planningHorizon = create_weeks(4)
all_nurses = range(len(nurses))
all_working_shifts = range(len(shiftTypes))
all_shifts = range(len(shiftTypes) + 1)
all_days = range(len(weekDays) * len(planningHorizon))
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
    opt_demand = []

    for w in range(len(wData)):
        for i in range(len(wDays)):
            head_early = 0
            head_late = 0
            head_night = 0

            nurse_early = 0
            nurse_late = 0
            nurse_night = 0

            opt_head_early = 0
            opt_head_late = 0
            opt_head_night = 0

            opt_nurse_early = 0
            opt_nurse_late = 0
            opt_nurse_night = 0
            for j in range(len(wData[w]['requirements'])):
                if wData[w]['requirements'][j]['skill'] == 'HeadNurse':
                    req = wData[w]['requirements'][j]['requirementOn'+ wDays[i]]
                    if wData[w]['requirements'][j]['shiftType'] == 'Early':
                        head_early += req['minimum']
                        opt_head_early += req['optimal']
                    elif wData[w]['requirements'][j]['shiftType'] == 'Late':
                        head_late += req['minimum']
                        opt_head_late += req['optimal']
                    elif wData[w]['requirements'][j]['shiftType'] == 'Night':
                        head_night += req['minimum']
                        opt_head_night += req['optimal']
                    else:
                        pass
                else:
                    req = wData[w]['requirements'][j]['requirementOn'+ wDays[i]]
                    if wData[w]['requirements'][j]['shiftType'] == 'Early':
                        nurse_early += req['minimum']
                        opt_nurse_early += req['optimal']
                    elif wData[w]['requirements'][j]['shiftType'] == 'Late':
                        nurse_late += req['minimum']
                        opt_nurse_late += req['optimal']
                    elif wData[w]['requirements'][j]['shiftType'] == 'Night':
                        nurse_night += req['minimum']
                        opt_nurse_night += req['optimal']
                    else:
                        pass
            headnurse_demand.append((head_early, head_late, head_night))
            nurse_demand.append((nurse_early, nurse_late, nurse_night))
            opt_demand.append((opt_head_early + opt_nurse_early, opt_head_late + opt_nurse_late, opt_head_night + opt_nurse_night))

    return headnurse_demand, nurse_demand, opt_demand

def find_indices(lst, condition):
    return [i for i, elem in enumerate(lst) if condition(elem)]

def create_request(wData, nurseList, shiftList, dayList):
    requests = []
    for w in range(len(wData)):
        for i in wData[w]['shiftOffRequests']:
            temp = [(find_indices(nurseList, lambda n: i['nurse'] in n.id)),
                    find_indices(shiftList, lambda n: i['shiftType'] in n.id),
                    find_indices(dayList, lambda n: i['day'] in n),
                    [10]]
            for j, k in enumerate(temp):
                if k == []:
                    temp[j] = [0]
            request = [x for x, in temp]
            request[2] = request[2] + (w * len(weekDays))
            requests.append(request)
    return requests

weekly_demand = create_weekly_demand(planningHorizon, weekDays)
requests = create_request(planningHorizon, nurses, shiftTypes, weekDays)
forbidden_shift_succession = create_forbidden_succession(scenarioDict)

print(weekly_demand)

obj_int_vars = []
obj_int_coeffs = []
obj_bool_vars = []
obj_bool_coeffs = []

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

# H2 H4 S1: Each shift is assigned to opt or min requirements of nurses depending on their skills.
for s in range(1, len(shiftTypes) + 1):
    print(s)
    for d in all_days:
        for f in range(len(skills)):
            works = [shifts[n, d, s] for n in find_indices(nurses, lambda n: skills[f] in n.skills)]
            min_demand = weekly_demand[f][d][s - 1]
            worked = model.NewIntVar(min_demand, len(find_indices(nurses, lambda n: skills[f] in n.skills)), '')
            model.Add(worked == sum(works))
        name = 'not optimal demand (shift=%i, day=%i)' % (s, d)
        insufficient = model.NewIntVar(0, len(nurses) - weekly_demand[2][d][s - 1], name)
        model.Add(insufficient == weekly_demand[2][d][s - 1] - worked)
        obj_int_vars.append(insufficient)
        obj_int_coeffs.append(30)



# H3: Forbidden shift successions
for previous_shift, next_shift, cost in forbidden_shift_succession:
    for n in all_nurses:
        for d in range((len(all_days) - 1)):
            transition = [shifts[n, d, previous_shift].Not(), shifts[n, d + 1, next_shift].Not()]
            model.AddBoolOr(transition)

test = [1,2,3]

# S5: Complete weekends
#TODO: Check why same shifts on weekends are alwasys choosen
for n in all_nurses:
    for w in range(len(planningHorizon)):
        for d in range(len(weekDays)):
            if (nurses[n].contract.completeWeekends == 1 and weekDays[d] == "Saturday"):
                sun_weekends = [shifts[n, d + (w * len(weekDays)), 0], shifts[n, d + (w * len(weekDays)) + 1, 0].Not()]
                sat_weekends = [shifts[n, d + (w * len(weekDays)), 0].Not(), shifts[n, d + (w * len(weekDays)) + 1, 0]]
                sun_week_var = model.NewBoolVar('complete weekend (employee=%i, week=%i)' % (n, w))
                sat_week_var = model.NewBoolVar('complete weekend (employee=%i, week=%i)' % (n, w))
                print(sun_weekends)
                sun_weekends.append(sun_week_var)
                sat_weekends.append(sat_week_var)
                model.AddBoolXOr(sun_weekends)
                model.AddBoolXOr(sat_weekends)
                obj_bool_vars.append(sun_week_var)
                obj_bool_coeffs.append(30)
                obj_bool_vars.append(sat_week_var)
                obj_bool_coeffs.append(30)


# S4: Preferences
for n, s, d, w in requests:
    preference = [shifts[n, d, s]]
    pref_var = model.NewBoolVar('preference (employee=%i, day=%i, shift=%i)' % (n, d, s))
    preference.append(pref_var)
    model.AddBoolOr(preference)
    obj_bool_vars.append(pref_var)
    obj_bool_coeffs.append(w)

print(obj_bool_vars)
print(obj_int_vars)
print(obj_int_coeffs)

model.Minimize(
    sum(obj_bool_vars[i] * obj_bool_coeffs[i]
    for i in range(len(obj_bool_vars))) +
    sum(obj_int_vars[i] * obj_int_coeffs[i]
    for i in range(len(obj_int_vars))))

# Solve the model.
solver = cp_model.CpSolver()
solution_printer = cp_model.ObjectiveSolutionPrinter()
status = solver.Solve(model, solution_printer)

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print()
    header = '          '
    for w in range(len(planningHorizon)):
        header += 'M T W T F S S '
    print(header)
    for n in all_nurses:
        schedule = ''
        for d in all_days:
            for s in all_shifts:
                if solver.BooleanValue(shifts[n, d, s]):
                    schedule += shiftRepr[s] + ' '
        print(' nurse %i: %s' % (n, schedule))

    print('Penalties:')
    for i, var in enumerate(obj_bool_vars):
        if solver.BooleanValue(var):
            penalty = obj_bool_coeffs[i]
            if penalty > 0:
                print('  %s violated, penalty=%i' % (var.Name(), penalty))
            else:
                print('  %s fulfilled, gain=%i' % (var.Name(), -penalty))

    for i, var in enumerate(obj_int_vars):
        if solver.Value(var) > 0:
            print('  %s violated by %i, linear penalty=%i' %
                  (var.Name(), solver.Value(var), obj_int_coeffs[i]))

print('\nStatistics')
print('  - status          : %s' % solver.StatusName(status))
print('  - conflicts      : %i' % solver.NumConflicts())
print('  - branches       : %i' % solver.NumBranches())
print('  - wall time      : %f s' % solver.WallTime())
print('  - solutions found: %i' % solution_printer.solution_count())


#df = pd.DataFrame(scenarioDict['nurses'])
#pd.set_option("max_colwidth", 40)
#print(df)
