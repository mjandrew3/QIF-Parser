# -*- coding: utf-8 -*-
"""This script aims to take a .QIF Quicken file as an import.  It will
then process the file and create separate flat files based on the section
from the QIF file.  

The currently supported sections are:
Tags
Category
Account
Transaction
Investment
Memorized
Security
Prices
"""


import datetime
import re

import numpy as np
import pandas as pd


#Import QIF datafile
data = open("Quicken Data.QIF",'r').read()
chunks = data.split('\n^\n')