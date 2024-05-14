import re


def fix_price(price):
    '''Fix all prices output from Quicken.

    '''
    if price == '':
        return 0
    if "/" in price:
        if " " in price:
            split = price.split(" ")
            split = float(split[0]) + eval(split[1])
        else:
            split = eval(price)
        return split
    else:
        return float(price)


def parse_cat(cat):
    '''Parse category outputs from Quicken

    '''
    tax = 'N'
    subcat = ''
    desc = ''
    inc_type = ''
    bud = ''
    tax_sched = ''
    for line in cat:
        match line[0]:
            case 'N':
                #Category name:subcategory name
                subcat = line[1:]
            case 'D':
                #Description
                desc = line[1:]
            case 'T':
                #Tax-related if included
                tax = 'Y'
            case 'I':
                #Income category
                inc_type = 'Income'
            case 'E':
                #Expense category
                inc_type = 'Expense'
            case 'B':
                #Budget Amount
                bud = line[1:]
            case 'R':
                #Tax Schedule Item
                tax_sched = line[1:]
    category = [subcat,desc,tax,inc_type,bud,tax_sched]
    return category


def parse_acct(acct):
    '''Parse Account details
    
    '''
    name = ''
    acct_type = ''
    desc = ''
    limit = ''
    bal_date = ''
    bal_amt = ''
    for line in acct:
        match line[0]:
            case 'N':
                #Name
                name = line[1:]
            case 'T':
                #Account Type
                acct_type = line[1:]
            case 'D':
                #Description
                desc = line[1:]
            case 'L':
                #Credit Limit
                limit = line[1:]
            case '/':
                #Statement Balance Date
                bal_date = line[1:]
            case '$':
                #Statement Balance Amount
                bal_amt = line[1:]
    account = [name,acct_type,desc,limit,bal_date,bal_amt]
    return account


def parse_tran(counter,account,tran):
    '''Parse Transaction Lines
    
    '''
    date=''
    amt= 0
    u_amt=0 #For multi-currency setups, I've based them in USD
    clear=''
    num=''
    payee=''
    memo=''
    address=''
    cat=''
    split_cat=[]
    split_memo=[]
    split_amt=[]
    new_tran=[]
    for line in tran:
        match line[0]:
            case 'D':
                #Date
                date=line[1:].replace("'","/").replace(" ","0")
            case 'T':
                #Amount
                amt=float(line[1:].replace(",",""))
            case 'U':
                #Amount
                u_amt=float(line[1:].replace(",",""))
            case 'C':
                #Cleared Status
                clear=line[1:]
            case 'N':
                #Num (check or reference number)
                num=line[1:]
            case 'P':
                #Payee
                payee=re.sub(' +',' ',line[1:])
            case 'M':
                #Memo
                memo=line[1:]
            case 'A':
                #Address (up to five lines; the sixth line is an optional message)
                address=line[1:]
            case 'L':
                #Category (Category/SubCategory/Transfer/Class)
                cat=line[1:]
            case 'S':
                #Category in Split (Category/Transfer/Class)
                split_cat.append(line[1:])
            case 'E':
                #Memo in split
                split_memo.append(line[1:])
            case '$':
                #Dollar amount of split
                split_amt.append(float(line[1:].replace(",","")))
    if len(split_cat) != len(split_memo):
        split_memo = split_memo + ['' for x in range(len(split_cat)-len(split_memo))]
    if split_cat==[]:
        new_tran.append([counter,account,date,u_amt,amt,clear,num,payee,memo,address,cat,'Single'])
    else:
        for x in range(len(split_cat)):
            new_tran.append([counter,account,date,u_amt,split_amt[x],clear,num,payee,split_memo[x],address,split_cat[x],'Split'])
    return new_tran


def parse_inv(counter,account,inv):
    '''Parse Investment Transactions
    
    '''
    date=''
    action=''
    security=''
    price=0
    qty=0
    amt=0
    clear=''
    text=''
    memo=''
    comm=0
    tran=''
    tran_amt=0
    for line in inv:
        match line[0]:
            case 'D':
                #Date
                date=line[1:].replace("'","/").replace(" ","0")
            case 'N':
                #Action
                action=line[1:]
            case 'Y':
                #Securiy
                security=re.sub(' +',' ',line[1:])
            case 'I':
                #Price
                price=float(line[1:].replace(",",""))
            case 'Q':
                #Quantity (number of shares or split ratio)
                qty=float(line[1:].replace(",",""))
            case 'T':
                #Transaction Amount
                amt=float(line[1:].replace(",",""))
            case 'C':
                #Cleared Status
                clear=line[1:]
            case 'P':
                #Text in the first line for transfers and reminders
                text=line[1:]
            case 'M':
                #Memo
                memo=line[1:]
            case 'O':
                #Commission
                comm=float(line[1:].replace(",",""))
            case 'L':
                #Account for the transfer
                tran=line[1:]
            case '$':
                #Amount transferred
                tran_amt=float(line[1:].replace(",",""))
    
    #Rename Category Names to match Transaction categories
    if tran == 'Interest Inc':
        action = 'IntInc'
    if tran != '' and (tran[0] == '[' or tran=='Financial') and action=='Cash':
        if amt < 0:
            amt = amt * -1
            action = 'XOut'
        elif amt == 0:
            action = 'Begin'
        else:
            action = 'XIn'
    elif tran == 'Div Income':
        action = 'Div'
    elif tran == 'Tax:Fed':
        action = 'Tax'
    elif tran == 'Fees & Charges:Bank Fee':
        if amt >= 0:
            action = 'XIn'
        else:
            action = 'Fee'
    if action == 'SellX' or action == 'BuyX':
        action = action.replace('X','')
    if action == 'Buy' and qty != int(qty):
        action = 'BuyDiv'
    investment = [counter,account,date,action,security,price,qty,amt,comm,clear,text,memo,tran,tran_amt]
    return investment