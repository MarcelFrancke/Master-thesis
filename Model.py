import copy
import itertools
import json
import os

import params as params
from numpy.random import random

from elements.Contract import Contract
from elements.Nurse import Nurse
from elements.Shift import Shift
from ortools.sat.python import cp_model
from absl import flags, app
from google.protobuf import text_format
import itertools
import csv
import matplotlib.pyplot as plt
import pandas as pd


def solve_shift_scheduling(params, weekList, instance, output_path):
    contracts = []
    nurses = []
    shiftTypes = []
    fieldnames = ["Solution", "Time", "Objective"]
    shiftRepr = ['-', 'E', 'D', 'L', 'N']
    weekDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekDaysSol = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    shiftReprSol = ['Off', 'Early', 'Day', 'Late', 'Night']
    model = cp_model.CpModel()

    with open('resources/datasets/' + instance +'/Sc-' + instance +'.json') as file:
        scenarioDict = json.load(file)

    with open(output_path + '/' + scenarioDict['id'] + '.csv', 'w', encoding='UTF8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

    def create_weeks(list):
        planningHorizon = []
        for i in range(len(list)):
            with open('resources/datasets/' + instance +'/WD-' + instance +'-' + str(list[i]) + '.json') as file:
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

        elif i.contract == "PartTime":
            setattr(i, "contract", contracts[1])

        elif i.contract == "HalfTime":
            setattr(i, "contract", contracts[2])

        else:
            setattr(i, "contract", contracts[3])

    skills = scenarioDict['skills']
    planningHorizon = create_weeks(weekList)
    all_nurses = range(len(nurses))
    all_working_shifts = range(len(shiftTypes))
    all_shifts = range(len(shiftTypes) + 1)
    all_days = range(len(weekDays) * len(planningHorizon))
    all_skills = range(len(skills))

    def create_sequence_constraints(scData):
        shift_sequence_constraints = []

        for i in range(len(scData['shiftTypes'])):
            shift_sequence_constraints.append((i + 1, scData['shiftTypes'][i]['minimumNumberOfConsecutiveAssignments'],
                                               scData['shiftTypes'][i]['minimumNumberOfConsecutiveAssignments'], 15,
                                               scData['shiftTypes'][i]['maximumNumberOfConsecutiveAssignments'],
                                               scData['shiftTypes'][i]['maximumNumberOfConsecutiveAssignments'], 15))
        return shift_sequence_constraints

    def create_day_off_sequence_constraints(scData):
        day_off_sequence_constraints = []

        for i in range(len(scData['contracts'])):
            day_off_sequence_constraints.append((scData['contracts'][i]['minimumNumberOfConsecutiveDaysOff'],
                                                 scData['contracts'][i]['minimumNumberOfConsecutiveDaysOff'], 30,
                                                 scData['contracts'][i]['maximumNumberOfConsecutiveDaysOff'],
                                                 scData['contracts'][i]['maximumNumberOfConsecutiveDaysOff'], 30))
        return day_off_sequence_constraints

    def create_forbidden_succession(scData):
        forbidden_array_str = []
        forbidden_array_int = []
        for i in range(len(scData['forbiddenShiftTypeSuccessions'])):
            if not scData['forbiddenShiftTypeSuccessions'][i]['succeedingShiftTypes']:
                pass
            else:
                if scData['forbiddenShiftTypeSuccessions'][i]['precedingShiftType'] == 'Early' or 'Day' or 'Late' or 'Night':
                    for j in range(len(scData['forbiddenShiftTypeSuccessions'][i]['succeedingShiftTypes'])):
                        forbidden_array_str.append((scData['forbiddenShiftTypeSuccessions'][i]['precedingShiftType'],
                                                scData['forbiddenShiftTypeSuccessions'][i]['succeedingShiftTypes'][j],
                                                0))
        for tuple in forbidden_array_str:
            temp = list(map(lambda x: 1 if x=='Early' else x,tuple))
            temp1 = list(map(lambda x: 2 if x=='Day' else x,temp))
            temp2 = list(map(lambda x: 3 if x=='Late' else x,temp1))
            temp3 = list(map(lambda x: 4 if x=='Night' else x,temp2))

            forbidden_array_int.append(temp3)

            #res = [item.replace('Early', 1) for item in forbidden_array[i]]

        return forbidden_array_int

    def create_weekly_demand(wData, wDays):
        min_demand = []
        opt_demand = []

        for k in all_skills:
            min_test1 = []
            opt_test1 = []
            for w in range(len(wData)):
                for i in range(len(wDays)):
                    min_test = [0] * len(shiftTypes)
                    opt_test = [0] * len(shiftTypes)
                    for j in range(len(wData[w]['requirements'])):
                        for s in all_working_shifts:
                            if wData[w]['requirements'][j]['skill'] == skills[k] and wData[w]['requirements'][j]['shiftType'] == shiftTypes[s].id:
                                min_test[s] += wData[w]['requirements'][j]['requirementOn'+ wDays[i]]['minimum']
                                opt_test[s] += wData[w]['requirements'][j]['requirementOn'+ wDays[i]]['optimal']
                    min_test1.append(min_test)
                    opt_test1.append(opt_test)
            min_demand.append(min_test1)
            opt_demand.append(opt_test1)
        return min_demand, opt_demand

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

    def negated_bounded_span(works, start, length):
        """Filters an isolated sub-sequence of variables assined to True.
      Extract the span of Boolean variables [start, start + length), negate them,
      and if there is variables to the left/right of this span, surround the span by
      them in non negated form.
      Args:
        works: a list of variables to extract the span from.
        start: the start to the span.
        length: the length of the span.
      Returns:
        a list of variables which conjunction will be false if the sub-list is
        assigned to True, and correctly bounded by variables assigned to False,
        or by the start or end of works.
      """
        sequence = []
        # Left border (start of works, or works[start - 1])
        if start > 0:
            sequence.append(works[start - 1])
        for i in range(length):
            sequence.append(works[start + i].Not())
        # Right border (end of works or works[start + length])
        if start + length < len(works):
            sequence.append(works[start + length])
        return sequence


    def add_soft_sequence_constraint(model, works, hard_min, soft_min, min_cost,
                                     soft_max, hard_max, max_cost, prefix):
        """Sequence constraint on true variables with soft and hard bounds.
      This constraint look at every maximal contiguous sequence of variables
      assigned to true. If forbids sequence of length < hard_min or > hard_max.
      Then it creates penalty terms if the length is < soft_min or > soft_max.
      Args:
        model: the sequence constraint is built on this model.
        works: a list of Boolean variables.
        hard_min: any sequence of true variables must have a length of at least
          hard_min.
        soft_min: any sequence should have a length of at least soft_min, or a
          linear penalty on the delta will be added to the objective.
        min_cost: the coefficient of the linear penalty if the length is less than
          soft_min.
        soft_max: any sequence should have a length of at most soft_max, or a linear
          penalty on the delta will be added to the objective.
        hard_max: any sequence of true variables must have a length of at most
          hard_max.
        max_cost: the coefficient of the linear penalty if the length is more than
          soft_max.
        prefix: a base name for penalty literals.
      Returns:
        a tuple (variables_list, coefficient_list) containing the different
        penalties created by the sequence constraint.
      """
        cost_literals = []
        cost_coefficients = []

        # Penalize sequences that are below the soft limit.
        if min_cost > 0:
            for length in range(hard_min, soft_min):
                for start in range(len(works) - length + 1):
                    span = negated_bounded_span(works, start, length)
                    name = ': under_span(start=%i, length=%i)' % (start, length)
                    lit = model.NewBoolVar(prefix + name)
                    span.append(lit)
                    model.AddBoolOr(span)
                    cost_literals.append(lit)
                    # We filter exactly the sequence with a short length.
                    # The penalty is proportional to the delta with soft_min.
                    cost_coefficients.append(min_cost * (soft_min - length))

        # Penalize sequences that are above the soft limit.
        if max_cost > 0:
            for length in range(soft_max + 1, hard_max + 1):
                for start in range(len(works) - length + 1):
                    span = negated_bounded_span(works, start, length)
                    name = ': over_span(start=%i, length=%i)' % (start, length)
                    lit = model.NewBoolVar(prefix + name)
                    span.append(lit)
                    model.AddBoolOr(span)
                    cost_literals.append(lit)
                    # Cost paid is max_cost * excess length.
                    cost_coefficients.append(max_cost * (length - soft_max))

        return cost_literals, cost_coefficients

    def add_soft_sum_constraint(model, works, hard_min, soft_min, min_cost,
                                soft_max, hard_max, max_cost, prefix):
        """Sum constraint with soft and hard bounds.
      This constraint counts the variables assigned to true from works.
      If forbids sum < hard_min or > hard_max.
      Then it creates penalty terms if the sum is < soft_min or > soft_max.
      Args:
        model: the sequence constraint is built on this model.
        works: a list of Boolean variables.
        hard_min: any sequence of true variables must have a sum of at least
          hard_min.
        soft_min: any sequence should have a sum of at least soft_min, or a linear
          penalty on the delta will be added to the objective.
        min_cost: the coefficient of the linear penalty if the sum is less than
          soft_min.
        soft_max: any sequence should have a sum of at most soft_max, or a linear
          penalty on the delta will be added to the objective.
        hard_max: any sequence of true variables must have a sum of at most
          hard_max.
        max_cost: the coefficient of the linear penalty if the sum is more than
          soft_max.
        prefix: a base name for penalty variables.
      Returns:
        a tuple (variables_list, coefficient_list) containing the different
        penalties created by the sequence constraint.
      """
        cost_variables = []
        cost_coefficients = []
        sum_var = model.NewIntVar(hard_min, hard_max, '')
        model.Add(sum_var == sum(works))

        # Penalize sums below the soft_min target.
        if soft_min > hard_min and min_cost > 0:
            delta = model.NewIntVar(-len(works), len(works), '')
            model.Add(delta == soft_min - sum_var)
            # TODO(user): Compare efficiency with only excess >= soft_min - sum_var.
            excess = model.NewIntVar(0, hard_max, prefix + ': under_sum')
            model.AddMaxEquality(excess, [delta, 0])
            cost_variables.append(excess)
            cost_coefficients.append(min_cost)

        # Penalize sums above the soft_max target.
        if soft_max < hard_max and max_cost > 0:
            delta = model.NewIntVar(-hard_max, hard_max, '')
            model.Add(delta == sum_var - soft_max)
            excess = model.NewIntVar(0, hard_max, prefix + ': over_sum')
            model.AddMaxEquality(excess, [delta, 0])
            cost_variables.append(excess)
            cost_coefficients.append(max_cost)

        return cost_variables, cost_coefficients

    weekly_demand = create_weekly_demand(planningHorizon, weekDays)
    requests = create_request(planningHorizon, nurses, shiftTypes, weekDays)
    forbidden_shift_succession = create_forbidden_succession(scenarioDict)
    shift_sequence_constraints = create_sequence_constraints(scenarioDict)
    day_off_sequence_constraints = create_day_off_sequence_constraints(scenarioDict)

    obj_int_vars = []
    obj_int_coeffs = []
    obj_bool_vars = []
    obj_bool_coeffs = []

    # Creates shift variables.
    shifts = {}
    for n in all_nurses:
        for d in all_days:
            for s in all_shifts:
                for f in range(len(nurses[n].skills)):
                    shifts[(n, d, s, nurses[n].skills[f])] = model.NewBoolVar('shift_n%id%is%if%s' % (n, d, s, nurses[n].skills[f]))


    # H1: Exactly one shift and one skill per day.
    for n in all_nurses:
        for d in all_days:
            model.AddExactlyOne((shifts[n, d, s, nurses[n].skills[f]] for s in all_shifts for f in range(len(nurses[n].skills))))

    # H3: Forbidden shift successions
    for previous_shift, next_shift, cost in forbidden_shift_succession:
        for n in all_nurses:
            for d in range((len(all_days) - 1)):
                if len(nurses[n].skills) == 1:
                    transition = [shifts[n, d, previous_shift, nurses[n].skills[0]].Not(),
                                  shifts[n, d + 1, next_shift, nurses[n].skills[0]].Not()]
                    model.AddBoolOr(transition)
                else:
                    temp_perm = [p for p in itertools.product(nurses[n].skills, repeat=2)]
                    for f in range(len(temp_perm)):
                        transition = [shifts[n, d, previous_shift, temp_perm[f][0]].Not(), shifts[n, d + 1, next_shift, temp_perm[f][1]].Not()]
                        model.AddBoolOr(transition)


    # H2 H4 S1: Each shift is assigned to opt or min requirements of nurses depending on their skills.
    for s in range(1, len(shiftTypes) + 1):
        for d in all_days:
            for f in range(len(skills)):
                works = [shifts[n, d, s, skills[f]] for n in find_indices(nurses, lambda n: skills[f] in n.skills)]
                min_demand = weekly_demand[0][f][d][s - 1]
                opt_demand = weekly_demand[1][f][d][s - 1]
                #worked = model.NewIntVar(min_demand, len(find_indices(nurses, lambda n: skills[f] in n.skills)), '')
                #model.Add(worked >= sum(works))
                name = 'not optimal demand (shift=%i, day=%i)' % (s, d)
                variables, coeffs = add_soft_sum_constraint(
                    model, works, min_demand, opt_demand, 30,
                    len(find_indices(nurses, lambda n: skills[f] in n.skills)), len(find_indices(nurses, lambda n: skills[f] in n.skills)), 30, name)
                # insufficient = model.NewIntVar(0, len(find_indices(nurses, lambda n: skills[f] in n.skills)) - weekly_demand[1][f][d][s - 1], name)
                # model.Add(insufficient <= weekly_demand[1][f][d][s - 1] - worked)
                obj_bool_vars.extend(variables)
                obj_bool_coeffs.extend(coeffs)

    # # S2: Consecutive shift assignment 1/2
    for ct in shift_sequence_constraints:
        shift, hard_min, soft_min, min_cost, hard_max, soft_max, max_cost = ct
        one_skill = find_indices(nurses, lambda n: len(n.skills) == 1)
        for n in range(len(one_skill)):
            works = [shifts[one_skill[n], d, shift, nurses[one_skill[n]].skills[0]] for d in all_days ]
            variables, coeffs = add_soft_sequence_constraint(
                model, works, 1, soft_min, min_cost, soft_max, len(all_days), max_cost, 'cons_shift_constraint(employee %i, shift %i)' % (n, shift))
            obj_bool_vars.extend(variables)
            obj_bool_coeffs.extend(coeffs)
    #
    # # S2: Consecutive work assignment 2/2
    for n in all_nurses:
        #for f in range(len(nurses[n].skills)):
        one_skill = find_indices(nurses, lambda n: len(n.skills) == 1)
        for n in range(len(one_skill)):
            works = [shifts[one_skill[n], d, 0, nurses[one_skill[n]].skills[0]].Not() for d in all_days]
            variables, coeffs = add_soft_sequence_constraint(
                model, works, 1, 3, 30, 5, len(all_days), 30, 'cons_work_constraint(employee %i)' % (n))
            obj_bool_vars.extend(variables)
            obj_bool_coeffs.extend(coeffs)

    # # S3: Consecutive Days Off
    for c in range(len(contracts)):
        cn = find_indices(nurses, lambda n: contracts[c].id == n.contract.id)
        for n in range(len(cn)):
            for f in range(len(nurses[cn[n]].skills)):
                hard_min, soft_min, min_cost, hard_max, soft_max, max_cost = day_off_sequence_constraints[c]
                works = [shifts[cn[n], d, 0, nurses[cn[n]].skills[f]] for d in all_days]
                variables, coeffs = add_soft_sequence_constraint(
                    model, works, 1, soft_min, min_cost, soft_max, len(all_days), max_cost, 'day_off_sequence_constraint(employee %i)' % (n))
                obj_bool_vars.extend(variables)
                obj_bool_coeffs.extend(coeffs)
    #
    # # S4: Preferences
    for n, s, d, w in requests:
        preference = [shifts[n, d, s, nurses[n].skills[f]] for f in range(len(nurses[n].skills))]
        pref_var = model.NewBoolVar('preference (employee=%i, day=%i, shift=%i)' % (n, d, s))
        preference.append(pref_var)
        model.AddBoolOr(preference)
        obj_bool_vars.append(pref_var)
        obj_bool_coeffs.append(w)
    #
    # # S5: Complete weekends
    for n in all_nurses:
        for w in range(len(planningHorizon)):
            for d in range(len(weekDays)):
                if (nurses[n].contract.completeWeekends == 1 and weekDays[d] == "Saturday"):
                    if len(nurses[n].skills) == 1:
                        sat_weekends = [shifts[n, d + (w * len(weekDays)), 0, nurses[n].skills[0]].Not(),
                                        shifts[n, d + (w * len(weekDays)) + 1, 0, nurses[n].skills[0]]]
                        sat_week_var = model.NewBoolVar('complete weekend (employee=%i, week=%i)' % (n, w))
                        sat_weekends.append(sat_week_var)
                        model.AddExactlyOne(sat_weekends)
                        obj_bool_vars.append(sat_week_var)
                        obj_bool_coeffs.append(30)
                    else:
                        temp_perm = [p for p in itertools.product(nurses[n].skills, repeat=2)]
                        for f in range(len(temp_perm)):
                            sat_weekends = [shifts[n, d + (w * len(weekDays)), 0, temp_perm[f][0]].Not(),
                                            shifts[n, d + (w * len(weekDays)) + 1, 0, temp_perm[f][1]]]
                            sat_week_var = model.NewBoolVar('complete weekend (employee=%i, week=%i)' % (n, w))
                            sat_weekends.append(sat_week_var)
                            model.AddExactlyOne(sat_weekends)
                            obj_bool_vars.append(sat_week_var)
                            obj_bool_coeffs.append(30)
    #
    # # S6: Total assignments
    for c in range(len(contracts)):
        cn = find_indices(nurses, lambda n: contracts[c].id == n.contract.id)
        for n in range(len(cn)):
            for f in range(len(nurses[cn[n]].skills)):
                works = [shifts[cn[n], d, 0, nurses[cn[n]].skills[f]].Not() for d in all_days]
                variables, coeffs = add_soft_sum_constraint(
                    model, works, 1, nurses[cn[n]].contract.minimumNumberOfAssignments, 20,
                    nurses[cn[n]].contract.maximumNumberOfAssignments, len(all_days), 20, 'total_assignments(employee %s, contract %s)' % (nurses[cn[n]].id, nurses[cn[n]].contract.id))
                obj_bool_vars.extend(variables)
                obj_bool_coeffs.extend(coeffs)
    #
    # # S7: Total working weekends
    for c in range(len(contracts)):
        cn = find_indices(nurses, lambda n: contracts[c].id == n.contract.id)
        for n in range(len(cn)):
            for d in range(len(weekDays)):
                if weekDays[d] == "Saturday":
                    works = [shifts[cn[n], d +(w * len(weekDays)), 0, nurses[cn[n]].skills[f]] for w in range(len(planningHorizon)) for f in range(len(nurses[cn[n]].skills))]
                    variables, coeffs = add_soft_sum_constraint(
                        model, works, 1, nurses[cn[n]].contract.maximumNumberOfWorkingWeekends, 30,
                        nurses[cn[n]].contract.maximumNumberOfWorkingWeekends, len(planningHorizon), 30, 'total_working_weekends(employee %s)' % (nurses[cn[n]].id))
                    obj_bool_vars.extend(variables)
                    obj_bool_coeffs.extend(coeffs)

    model.Minimize(
        sum(obj_bool_vars[i] * obj_bool_coeffs[i]
        for i in range(len(obj_bool_vars))) +
        sum(obj_int_vars[i] * obj_int_coeffs[i]
        for i in range(len(obj_int_vars))))

    # if proto:
    #     print('Writing proto to %s' % proto)
    #     with open(proto + instance, 'w') as text_file:
    #         text_file.write(str(model))

    # Solve the model.
    solver = cp_model.CpSolver()
    if params:
        text_format.Parse(params, solver.parameters)
    solution_printer = cp_model.ObjectiveSolutionPrinter(scenarioDict['id'], output_path)
    #solver.parameters.num_search_workers = 30
    status = solver.Solve(model, solution_printer)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print()
        header = '          '
        dicts = []
        for w in range(len(planningHorizon)):
            dicts.append({
                "scenario": scenarioDict['id'],
                "week": w,
                "assignments": [],
            })
            for n in all_nurses:
                for d in range(len(weekDays)):
                    for s in range(1, len(shiftTypes) + 1):
                        for f in range(len(nurses[n].skills)):
                            if solver.BooleanValue(shifts[n, d +(w * len(weekDays)) , s, nurses[n].skills[f]]):
                                dicts[w]["assignments"].append({
                                    "nurse": nurses[n].id,
                                    "day": weekDaysSol[d],
                                    "shiftType": shiftReprSol[s],
                                    "skill": nurses[n].skills[f]
                                    }
                                )
        # Serializing json
        for w in range(len(weekList)):
            json_object = json.dumps(dicts[w], indent=4)

            # Writing to sample.json
            with open(output_path +"/Sol-"+ scenarioDict['id'] +"-" + str(weekList[w]) + ".json", "w") as outfile:
                outfile.write(json_object)
        print(dicts)

        print()
        header = '          '
        for w in range(len(planningHorizon)):
            header += 'M T W T F S S '
        print(header)
        for n in all_nurses:
            schedule = ''
            for d in all_days:
                for s in all_shifts:
                    for f in range(len(nurses[n].skills)):
                        if solver.BooleanValue(shifts[n, d, s, nurses[n].skills[f]]):
                            schedule += shiftRepr[s] + ' '
            print(' nurse %i: %s' % (n, schedule))

        print()
        header = '          '
        for w in range(len(planningHorizon)):
            header += 'M T W T F S S '
        print(header)
        for n in all_nurses:
            skill_schedule = ''
            for d in all_days:
                for s in all_shifts:
                    for f in range(len(nurses[n].skills)):
                        if solver.BooleanValue(shifts[n, d, s, nurses[n].skills[f]]):
                            skill_schedule += str(skills.index(nurses[n].skills[f])) + ' '
            print(' nurse %i: %s' % (n, skill_schedule))

        print('Penalties:')
        for i, var in enumerate(obj_bool_vars):
            if solver.BooleanValue(var):
                penalty = obj_bool_coeffs[i]
                if penalty > 0:
                    print('  %s violated, penalty=%i' % (var.Name(), penalty))

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
    print(solver.SolutionInfo())
    print(solver.ResponseStats())

    with open(output_path + '/' + "response_stats.txt", 'w') as f:
        f.write(solver.ResponseStats())

    df = pd.read_csv(output_path + '/' + scenarioDict['id'] + '.csv',sep=',')
    plot = df.plot(x='Time', y='Objective')
    fig = plot.get_figure()
    fig.savefig(output_path + "/" + 'plot.png')

def main(_):
    # n030w4_1_6-2-9-1
    FLAGS = flags.FLAGS

    parent_path = "/Users/marcelfrancke/PycharmProjects/Masterarbeit/resources/datasets/Solutions/"

    instances = [30, 35, 40]
    weekData = [[[6, 2, 9, 1], [6, 7, 5, 3]],
                [[1, 7, 1, 8], [4, 2, 6, 1], [5, 9, 5, 6], [9, 8, 7, 7], [0, 6, 9, 2], [8, 6, 7, 1]],
                [[2, 0, 6, 1], [6, 1, 0, 6]]
                ]
    num_iterations = 10

    for i in range(len(instances)):
        flags.DEFINE_string('params' + str(i), 'max_time_in_seconds:' + str(4 * (60 + 6 * instances[i])) + '',
                            'Sat solver parameters.')
        for j in range(len(weekData[i])):
            week_comb_path = "-".join(str(x) for x in weekData[i][j])
            inst_week_path = os.path.join(parent_path + 'n0' + str(instances[i]) + 'w4/', week_comb_path)
            os.mkdir(inst_week_path)
            for k in range(num_iterations):
                num_exp_path = os.path.join(inst_week_path, "sol_" + str(k) + "")
                os.mkdir(num_exp_path)

                # Runntime formel w×(60+6×n)
                if i == 0:
                    solve_shift_scheduling(FLAGS.params0, weekData[i][j], 'n0' + str(instances[i]) + 'w4', num_exp_path)
                elif i == 1:
                    solve_shift_scheduling(FLAGS.params1, weekData[i][j], 'n0' + str(instances[i]) + 'w4', num_exp_path)
                else:
                    solve_shift_scheduling(FLAGS.params2, weekData[i][j],
                                           'n0' + str(instances[i]) + 'w4', num_exp_path)


if __name__ == '__main__':
    app.run(main)

