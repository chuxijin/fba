#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

ModuleType = Literal['review', 'practice', 'wrong_review', 'ability']
RefType = Literal['content', 'question_set', 'wrong_dynamic', 'ability_task']
ItemStatus = Literal['pending', 'in_progress', 'completed', 'skipped']
PlanStatus = Literal['active', 'paused', 'finished']
