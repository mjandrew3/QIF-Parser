# QIF-Parser
Python Parser of QIF Quicken output file

This script will read a .QIF file from Quicken and parse the contents to output X files:
    - Tags: Shows the specific tags you may have utilized, such as "Tax Related" or "Vacation"
    - Categories: Shows a breakdown of all the categories with their descriptions, Categorization, and Tax Schedule
    - Accounts: Shows a breakdown of all accounts included
    - Securities: Shows all securities that are included
    - Transactions: Shows all transactions that have been entered.  Split transactions are shown as 2 separate lines where 'U-Amount' is the total amount of the transaction and 'Amount' is each individual lines' amount
    - Investments: Shows all investment transactions that have been entered.  Script currently supports stocks, bonds, options, and mutual funds.
    - Prices: Shows all prices for securities that have been downloaded