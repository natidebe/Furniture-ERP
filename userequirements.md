[10/4/2026 5:42 PM] Nati Man: Office Furniture Sales & Stock Telegram Bot
Business Model
We are an importer and seller of office furniture.
Our main sales are not online sales. Customers usually:
Come physically to our shop and see the furniture samples.
Order/buy directly from the shop.
Some customers are other furniture shops/resellers who buy from us and sell to their own customers.
Some customers from other cities such as Jimma, Bahir Dar, Mekele, etc. order by phone and we prepare the goods for them.
Reseller/shop customers often buy on credit.
Walk-in customers usually pay immediately.
We currently have:
Piassa branch — 1st branch, which handles most sales.
Denbel branch — 2nd branch.
Pawlos store/warehouse, where most of our stock is kept.
A small underground store at the Piassa branch for items already available at the shop.
The bot should be designed around this actual process.
⸻
Product Information
Every product should have its own:
Product name
Product code
Category
Unit
Selling price
Cost price (admin/accountant only)
Current stock
Stock location
Example categories:
Office chairs
Visitor chairs
Executive chairs
Desks
Tables
Shelves
Cabinets
Other office furniture
The product code is important because we currently identify products by their name and code on delivery papers.
⸻
Sales Process
A. Customer comes to Piassa shop
The salesperson shows the customer the available samples.
If the customer wants a small quantity and the product is already available in the Piassa shop:
Salesperson selects the customer.
Selects the product.
Enters quantity.
Selects the payment type.
Creates a delivery/sales document.
Stock is reduced from the Piassa shop stock.
The sale is recorded.
⸻
When the Product Is Not Available at Piassa
If the customer wants more quantity than we have at Piassa, or the product is not available in the shop:
The salesperson creates a stock request from Pawlos warehouse.
The request should contain:
Date
Requesting branch: Piassa
Product name
Product code
Quantity
Customer/order reference
Salesperson
Any notes
The request should immediately be sent/visible to the Pawlos storekeeper through Telegram.
The storekeeper then:
Receives the request.
Checks the Pawlos stock.
Takes the requested items out of the warehouse.
Confirms the quantity actually released.
The system records the stock movement.
The Pawlos storekeeper must not be able to release stock without a valid delivery/stock request.
⸻
Delivery Paper System
Currently, we use a physical delivery pad.
Each delivery paper contains:
Date
Customer name
Product name
Product code
Quantity
Other necessary sales information
The delivery paper has 3 copies:
One copy → Pawlos storekeeper
One copy → Accountant
One copy → remains in the delivery pad
The Telegram bot should replace or digitize this process.
Instead of sending a photo of a handwritten delivery paper, the salesperson should create the request in the bot.
The bot should generate a unique delivery/order number so that everyone can track the same transaction.
⸻
Stock Management
The system should maintain separate stock balances for each location.
For example:
Piassa Shop
Product A: 10 pcs
Product B: 5 pcs
Denbel Branch
Product A: 7 pcs
Product B: 3 pcs
Pawlos Warehouse
Product A: 100 pcs
Product B: 50 pcs
The system should show:
Total company stock = Piassa + Denbel + Pawlos
But each location must also have its own stock.
⸻
Stock Movement
The system should record every stock movement.
Examples:
Stock OUT from Pawlos
Pawlos → Piassa
Stock IN at Piassa
Piassa receives products from Pawlos.
Sale from Piassa
Piassa → Customer
Sale from Denbel
Denbel → Customer
The system should never simply change the stock number without recording why the stock changed.
Every stock movement should have:
Date
Product
Product code
Quantity
From location
To location/customer
Person responsible
Reference/order number
⸻
Payment Types
We have different payment situations.
A. Receipt / Official Sale
If the sale is made with an official receipt:
The payment must go to the organization/company bank account.
The system should record:
Sale amount
[10/4/2026 5:42 PM] Nati Man: Receipt number
Payment method
Organization account
Date
Customer
Salesperson
⸻
B. Sale Without Receipt
If a sale is made without an official receipt:
The payment is recorded separately as a personal account/payment, according to our existing process.
This should be kept separate from official organization-account payments.
The system should clearly identify the payment/account used.
⸻
C. Credit Sale
Some customers, especially reseller/shop customers, buy products on credit.
For a credit sale:
Sale is recorded.
Stock is reduced.
The amount becomes an outstanding customer balance.
The transaction is added to the customer’s credit account.
When the customer pays later, the payment is recorded against that credit balance.
The system should therefore have a customer credit ledger.
⸻
Customer Management
We need customer records.
Customer information can include:
Customer name
Phone number
Shop/company name
City
Customer type
Credit status
Total purchases
Total paid
Outstanding balance
Customer types could include:
Walk-in Customer
Usually purchases directly from the shop and pays immediately.
Reseller / Shop Customer
Buys furniture from us to resell.
Out-of-City Customer
Customers from places such as:
Jimma
Bahir Dar
Mekele
Other cities
These customers may order by phone.
⸻
Out-of-City Orders
The system should also support orders received by phone.
Example:
A furniture shop in Jimma calls and orders:
10 office chairs
5 visitor chairs
2 desks
The salesperson enters the order into the bot.
The order should have a status such as:
Pending → Confirmed → Prepared → Released
The system should keep the order connected to the customer and payment/credit information.
We do not currently provide our own delivery service, so the system should not assume that our company delivers to the customer.
⸻
Salesperson
A salesperson should be able to:
Search products
Check available stock
Check prices
Create a customer
Create a sale
Create a stock request
Create an order
Select payment type
Record customer credit
View their own sales
View order status
But salespeople should not be able to change important financial or stock information without permission.
⸻
Pawlos Storekeeper
The storekeeper should be able to:
See stock requests
See which branch/customer/order requested the products
Confirm stock availability
Release products
Record actual quantity released
Confirm the delivery/stock movement
View Pawlos warehouse stock
Important:
The storekeeper should not release products without an approved/requested transaction in the system.
⸻
Accountant
The accountant should be able to:
View all sales
View delivery documents
View stock movements
Record official payments
Record other payments
Manage customer credit
Record credit payments
View outstanding balances
Check receipts
Export data to Excel
Correct transactions when authorized
Generate financial reports
The accountant should effectively have the digital version of the current Excel stock/accounting process.
⸻
Admin
Admin should have full access.
Admin can:
Add/edit products
Change prices
Add users
Set user permissions
Add branches/locations
Add payment accounts
Correct transactions
View all sales
View all stock
View all customers
View all reports
View activity/history
Every important change should record:
Who changed it + what was changed + date/time.
⸻
Reports
The bot should automatically generate reports.
Daily Sales Report
For example:
Daily Sales — 03/10/2026
Total sales
Number of transactions
Cash/paid sales
Credit sales
Official receipt sales
Other payment sales
Sales by salesperson
Sales by branch
Products sold
Quantity sold
⸻
Weekly Report
Total weekly sales
Paid amount
Credit amount
Outstanding credit
Sales by salesperson
Sales by branch
Best-selling products
Stock movements
⸻
Monthly Report
Total monthly sales
Total paid
Total credit
Credit collected
Outstanding customer balances
Product sales quantities
Salesperson sales
Branch sales
Stock movements
⸻
Yearly Report
Same information for the full year, with monthly breakdowns.
⸻
Stock Reports
The bot should provide:
Current Stock
For example: 
[10/4/2026 5:42 PM] Nati Man: Product Piassa Denbel Pawlos Total Office Chair A 10 5 100 115 Desk B 4 2 30 36
Low Stock Alert
Admin can set a minimum stock level.
Example:
Office Chair A:
Minimum stock: 10
Current stock: 7
Bot sends:
⚠️ LOW STOCK Office Chair A Current stock: 7 pcs Minimum: 10 pcs
⸻
Important Requirement: Complete Transaction History
Every sale, stock movement, payment, credit transaction and correction should have a history.
For example:
Transaction #PS-2026-00125
Customer: ABC Furniture Product: Visitor Chair Code: VC-001 Quantity: 20 Salesperson: _ Source: Pawlos Destination: Piassa Payment: Credit Date: _ Status: Completed
This transaction should remain searchable later.
⸻
Search
The bot should make searching very easy.
Search by:
Product name
Product code
Customer name
Customer phone
Order number
Delivery number
Receipt number
Salesperson
Date
For example:
VC-001
should immediately show:
Product name
Price
Piassa stock
Denbel stock
Pawlos stock
Total stock
⸻
Telegram Interface
The bot should preferably use simple buttons instead of requiring users to type commands.
For example, salesperson sees:
🏠 MAIN MENU
[🛒 New Sale] [📦 Request Stock] [🔍 Check Stock] [👤 Customers] [💳 Credit] [📋 My Orders] [📊 My Sales]
Storekeeper sees:
[📦 Stock Requests] [🏭 Pawlos Stock] [🚚 Release Stock] [📋 Stock History]
Accountant sees:
[💰 Sales] [💳 Payments] [📒 Credit] [📦 Stock] [📊 Reports] [📄 Export Excel]
Admin sees everything.
⸻
Main Goal
The main goal is to replace our current manual process:
Customer → Salesperson → Handwritten Delivery Paper → Telegram Photo → Pawlos Storekeeper → Physical Stock → Accountant → Excel
with:
Customer → Salesperson enters transaction in Telegram Bot → Stock Request/Sale Created → Storekeeper receives request → Stock Movement Recorded → Accountant automatically sees transaction → Reports automatically updated
The system should make the process faster, reduce manual writing, reduce stock mistakes, and allow management to know the current stock, sales, payments and customer credit at any time.
[10/4/2026 5:43 PM] Nati Man: Payment and Pricing Requirements
Do Not Record Product Cost
The system does not need to record the purchasing/import cost of products.
For each product, we only need information such as:
Product name
Product code
Selling price
Quantity/stock
Location
There should be no cost-price field or cost/profit calculation in the system.
⸻
Payment Must Be Recorded Separately
The bot must have a proper payment-recording system.
A sale and a payment should not necessarily be the same transaction because a customer may:
Pay immediately
Pay later
Pay partially
Pay for only some of the items
Pay the remaining balance later
Therefore, every payment should be recorded against the relevant customer/order/sale.
⸻
Payment Account
Every payment must specify where the money was received.
There are two main account types:
Organization Account
Payment received through the organization’s official account.
The system should record:
Amount
Date
Customer
Related sale/order
Account: Organization
Payment method/account details if needed
Receipt number, if applicable
Personal Account
Payment received through a personal account according to our current business process.
The system should record:
Amount
Date
Customer
Related sale/order
Account: Personal
Payment method/account details if needed
The system must clearly distinguish between Organization and Personal payments.
⸻
Partial Payment
Example:
Customer buys products worth 100,000 ETB.
They pay:
40,000 ETB today → Organization Account
20,000 ETB later → Personal Account
Remaining 40,000 ETB → Credit
The system should show:
Total Sale: 100,000 ETB Paid: 60,000 ETB Credit/Remaining: 40,000 ETB
And payment history:
Date Amount Account Status 03/10/2026 40,000 Organization Paid 05/10/2026 20,000 Personal Paid
Remaining balance: 40,000 ETB
⸻
Payment for Specific Items
The system should also allow a payment to be connected to specific items when necessary.
For example:
Order contains:
10 chairs — 50,000 ETB
2 desks — 40,000 ETB
1 cabinet — 20,000 ETB
Customer may pay for the chairs first.
The salesperson/accountant should be able to record:
Payment: 50,000 ETB For: 10 chairs Account: Organization
The remaining items can stay unpaid/credit.
⸻
Customer Credit
For customers buying on credit, the bot should maintain a running balance.
For every customer:
Total purchases Total payments Outstanding balance
When the customer pays later, the accountant can select the customer and record the payment.
Example:
ABC Furniture
Total purchases: 500,000 ETB Payments: 350,000 ETB Outstanding: 150,000 ETB
The payment history should show exactly when each payment was made and whether it went to the Organization or Personal account.
⸻
Payment Reports
The system should be able to generate:
Organization Account
Total payments received
Daily
Weekly
Monthly
Yearly
Personal Account
Total payments received
Daily
Weekly
Monthly
Yearly
Combined
Total money received from all accounts
The reports should also allow filtering by:
Date
Customer
Salesperson
Branch
Order
Account type
⸻
Important Permission
Salespeople can record/select the payment information they are authorized to enter, but the accountant/admin should be able to verify and correct payment records.
Every payment should have a permanent history showing:
Who recorded it → amount → account → date/time → related sale/customer.