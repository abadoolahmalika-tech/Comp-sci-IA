import datetime as dt
import sqlite3
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas


# ---- your dad's business details go here once - never asked per booking, just reused every invoice ----
COMPANY_NAME = "Your Company Name"
COMPANY_ADDRESS = "123 Example Street, London, UK"

# the colour scheme used throughout the gui - change these to change the whole app's look
BG_COLOUR = "#f4f1ec"
ACCENT_COLOUR = "#3f6357"
ACCENT_TEXT_COLOUR = "#ffffff"
TABLE_HEADER_COLOUR = "#e4ded2"


# a property just needs an id (from the database) and a name
class Property:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    # tries to save a new booking for this property
    # returns (True, message, booking_id) if it worked, (False, message, None) if it clashed
    def saveBooking(self, guest, address, check_in_date, check_out_date, rate, fee):
        cursor.execute(
            "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ?",
            (self.id,)
        )
        existing_bookings = cursor.fetchall()

        for booking in existing_bookings:
            booking_check_in = dt.date.fromisoformat(booking[2])
            booking_check_out = dt.date.fromisoformat(booking[3])
            if booking_check_in <= check_in_date <= booking_check_out:
                return False, "dates taken (check-in falls inside an existing booking)", None
            elif booking_check_in <= check_out_date <= booking_check_out:
                return False, "dates taken (check-out falls inside an existing booking)", None
            elif check_in_date <= booking_check_in and booking_check_out <= check_out_date:
                return False, "dates taken (an existing booking lies inside your chosen dates)", None

        cursor.execute(
            """INSERT INTO bookings (property_id, guest, address, check_in, check_out, rate, fee)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self.id, guest, address, check_in_date.isoformat(), check_out_date.isoformat(), rate, fee)
        )
        conn.commit()
        return True, "booking saved", cursor.lastrowid  # lastrowid is the id sqlite just gave this new row

    # grabs every booking for this property, in the order they were added
    def getBookings(self):
        cursor.execute(
            "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ? ORDER BY id",
            (self.id,)
        )
        return cursor.fetchall()

    # deletes one booking by its database id
    def deleteBookingById(self, booking_id):
        cursor.execute("SELECT check_out FROM bookings WHERE id = ?", (booking_id,))
        row = cursor.fetchone()
        if row is None:
            return False, "booking not found"
        check_out = dt.date.fromisoformat(row[0])
        if check_out < dt.date.today():
            return False, "cannot delete a past booking"
        cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()
        return True, "booking deleted"

    # case-insensitive "contains" search on guest name
    def searchByName(self, search):
        rows = self.getBookings()
        return [b for b in rows if search.lower() in b[1].lower()]

    # builds a proper itemised pdf invoice using reportlab, with colour and a full breakdown
    def createInvoice(self, booking_id, guest, address, check_in_date, check_out_date, rate, fee):
        check_in_str = check_in_date.strftime("%d/%m/%Y")
        check_out_str = check_out_date.strftime("%d/%m/%Y")
        nights = (check_out_date - check_in_date).days

        subtotal = fee
        vat = round(subtotal * 0.2, 2)
        total = round(subtotal + vat, 2)

        c = canvas.Canvas("invoice.pdf", pagesize=letter)
        width, height = letter

        # ---- header band with the invoice title, in the accent colour ----
        c.setFillColor(colors.HexColor(ACCENT_COLOUR))
        c.rect(0, height - 100, width, 100, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(50, height - 65, "INVOICE")

        # ---- company details, top right, inside the header band ----
        c.setFont("Helvetica", 10)
        c.drawRightString(width - 50, height - 35, COMPANY_NAME)
        c.drawRightString(width - 50, height - 50, COMPANY_ADDRESS)

        c.setFillColor(colors.black)
        y = height - 130

        # ---- invoice metadata: number and date ----
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Invoice #" + str(booking_id))
        c.drawRightString(width - 50, y, "Date: " + dt.date.today().strftime("%d/%m/%Y"))
        y -= 30

        # ---- billed to section ----
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Billed to:")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(50, y, guest)
        y -= 14
        c.drawString(50, y, address)
        y -= 14
        c.drawString(50, y, "Property: " + self.name)
        y -= 14
        c.drawString(50, y, "Stay: " + check_in_str + " to " + check_out_str)
        y -= 30

        # ---- the itemised table ----
        table_top = y
        row_height = 22

        # header row of the table, shaded
        c.setFillColor(colors.HexColor(TABLE_HEADER_COLOUR))
        c.rect(50, table_top - row_height, width - 100, row_height, fill=True, stroke=False)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(55, table_top - row_height + 6, "Description")
        c.drawString(330, table_top - row_height + 6, "Nights")
        c.drawString(410, table_top - row_height + 6, "Unit Price")
        c.drawRightString(width - 55, table_top - row_height + 6, "Amount")

        y = table_top - row_height

        # the one line item - the stay itself
        c.setFont("Helvetica", 10)
        c.drawString(55, y - row_height + 6, "Accommodation (" + self.name + ")")
        c.drawString(330, y - row_height + 6, str(nights))
        c.drawString(410, y - row_height + 6, "£" + str(rate))
        c.drawRightString(width - 55, y - row_height + 6, "£" + str(subtotal))
        y -= row_height

        c.setLineWidth(0.5)
        c.line(50, y, width - 50, y)
        y -= 25

        # ---- totals box, right aligned ----
        c.setFont("Helvetica", 11)
        c.drawString(370, y, "Subtotal:")
        c.drawRightString(width - 55, y, "£" + str(subtotal))
        y -= 18

        c.drawString(370, y, "VAT (20%):")
        c.drawRightString(width - 55, y, "£" + str(vat))
        y -= 18

        c.setLineWidth(0.5)
        c.line(370, y + 5, width - 50, y + 5)
        y -= 15

        c.setFillColor(colors.HexColor(ACCENT_COLOUR))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(370, y, "Total:")
        c.drawRightString(width - 55, y, "£" + str(total))

        c.save()


# set up the database connection once, right at the start, so every function can use it
conn = sqlite3.connect("bookings.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER,
        guest TEXT,
        address TEXT,
        check_in TEXT,
        check_out TEXT,
        rate REAL,
        fee REAL
    )
""")
conn.commit()

# these two columns (address, rate) are new - if you're running this on an existing bookings.db
# that was made before this version, "CREATE TABLE IF NOT EXISTS" won't add them on its own,
# since the table already exists. these two lines add them in, and just get ignored (via the
# try/except) if they're already there from a fresh database
try:
    cursor.execute("ALTER TABLE bookings ADD COLUMN address TEXT")
except sqlite3.OperationalError:
    pass
try:
    cursor.execute("ALTER TABLE bookings ADD COLUMN rate REAL")
except sqlite3.OperationalError:
    pass
conn.commit()

current_property = None

root = tk.Tk()
root.title("Booking System")
root.geometry("560x500")
root.configure(bg=BG_COLOUR)

# this sets up how the table (ttk.Treeview) and its buttons look, since plain tk widgets
# take colours directly (bg=...) but ttk widgets need a "style" configured like this instead
style = ttk.Style()
style.theme_use("default")
style.configure("Treeview", background="white", fieldbackground="white", rowheight=26, font=("Helvetica", 10))
style.configure("Treeview.Heading", background=TABLE_HEADER_COLOUR, font=("Helvetica", 10, "bold"))
style.map("Treeview", background=[("selected", ACCENT_COLOUR)], foreground=[("selected", "white")])


def clearScreen():
    widget_list = root.winfo_children()
    for widget in widget_list:
        widget.destroy()


# a little helper so every button in the app looks the same, instead of repeating the same
# colour options on every single tk.Button(...) call
def makeButton(parent, text, command):
    return tk.Button(
        parent, text=text, command=command,
        bg=ACCENT_COLOUR, fg=ACCENT_TEXT_COLOUR,
        activebackground=ACCENT_COLOUR, activeforeground=ACCENT_TEXT_COLOUR,
        font=("Helvetica", 10, "bold"), relief="flat", padx=10, pady=5
    )


# ============================================================
# SCREEN 1: choose a property
# ============================================================

def showPropertyScreen():
    clearScreen()
    global current_property
    current_property = None

    title = tk.Label(root, text="Select a property", font=("Helvetica", 16, "bold"), bg=BG_COLOUR)
    title.pack(pady=10)

    property_listbox = tk.Listbox(root, width=40)
    property_listbox.pack(pady=10)

    cursor.execute("SELECT id, name FROM properties")
    property_rows = cursor.fetchall()
    for row in property_rows:
        property_listbox.insert(tk.END, row[1])

    def onSelectClicked():
        selected_index = property_listbox.curselection()
        if not selected_index:
            messagebox.showerror("Error", "Click a property first")
            return
        index = selected_index[0]
        chosen_row = property_rows[index]
        global current_property
        current_property = Property(chosen_row[0], chosen_row[1])
        showBookingsScreen()

    makeButton(root, "Select Property", onSelectClicked).pack(pady=5)

    add_label = tk.Label(root, text="Or add a new property:", bg=BG_COLOUR)
    add_label.pack(pady=(20, 0))

    name_entry = tk.Entry(root)
    name_entry.pack()

    def onAddClicked():
        name = name_entry.get()
        if name == "":
            messagebox.showerror("Error", "Enter a property name")
            return
        cursor.execute("INSERT INTO properties (name) VALUES (?)", (name,))
        conn.commit()
        showPropertyScreen()

    makeButton(root, "Add Property", onAddClicked).pack(pady=5)


# ============================================================
# SCREEN 2: the main "Bookings" table screen
# ============================================================

def showBookingsScreen():
    clearScreen()
    root.title("Bookings - " + current_property.name)

    top_frame = tk.Frame(root, bg=BG_COLOUR)
    top_frame.pack(fill="x", padx=10, pady=10)

    tk.Label(top_frame, text="Search:", bg=BG_COLOUR).pack(side="left")
    search_entry = tk.Entry(top_frame)
    search_entry.pack(side="left", fill="x", expand=True, padx=5)

    columns = ("name", "checkin", "checkout", "cost")
    table = ttk.Treeview(root, columns=columns, show="headings", height=12)
    table.heading("name", text="Name")
    table.heading("checkin", text="Check-in")
    table.heading("checkout", text="Check-out")
    table.heading("cost", text="Cost")
    table.column("name", width=140)
    table.column("checkin", width=100)
    table.column("checkout", width=100)
    table.column("cost", width=80)
    table.pack(padx=10, pady=5, fill="both", expand=True)

    row_id_lookup = {}

    def loadRows(bookings_to_show):
        table.delete(*table.get_children())
        row_id_lookup.clear()
        for booking in bookings_to_show:
            booking_id, guest, check_in, check_out, fee = booking
            check_in_str = dt.date.fromisoformat(check_in).strftime("%d/%m/%y")
            check_out_str = dt.date.fromisoformat(check_out).strftime("%d/%m/%y")
            row = table.insert("", tk.END, values=(guest, check_in_str, check_out_str, "£" + str(fee)))
            row_id_lookup[row] = booking_id

    loadRows(current_property.getBookings())

    def onSearchChanged(event):
        search_text = search_entry.get()
        if search_text == "":
            loadRows(current_property.getBookings())
        else:
            loadRows(current_property.searchByName(search_text))

    search_entry.bind("<KeyRelease>", onSearchChanged)

    button_frame = tk.Frame(root, bg=BG_COLOUR)
    button_frame.pack(fill="x", padx=10, pady=10)

    def onAddBookingClicked():
        openAddBookingWindow(onBookingSaved=lambda: loadRows(current_property.getBookings()))

    def onDeleteBookingClicked():
        selected = table.selection()
        if not selected:
            messagebox.showerror("Error", "Click a booking in the table first")
            return
        selected_row = selected[0]
        booking_id = row_id_lookup[selected_row]

        success, message = current_property.deleteBookingById(booking_id)
        if not success:
            messagebox.showerror("Error", message)
        else:
            loadRows(current_property.getBookings())

    makeButton(button_frame, "Add booking", onAddBookingClicked).pack(side="left", padx=5)
    makeButton(button_frame, "Delete booking", onDeleteBookingClicked).pack(side="left", padx=5)
    makeButton(button_frame, "Switch property", showPropertyScreen).pack(side="right", padx=5)


# ============================================================
# the "Add booking" popup window
# ============================================================

def openAddBookingWindow(onBookingSaved):
    popup = tk.Toplevel(root)
    popup.title("Add booking")
    popup.geometry("320x420")
    popup.configure(bg=BG_COLOUR)

    tk.Label(popup, text="Name", bg=BG_COLOUR).pack(pady=(15, 0))
    name_entry = tk.Entry(popup)
    name_entry.pack()

    tk.Label(popup, text="Address", bg=BG_COLOUR).pack(pady=(10, 0))
    address_entry = tk.Entry(popup, width=35)
    address_entry.pack()

    rate_frame = tk.Frame(popup, bg=BG_COLOUR)
    rate_frame.pack(pady=(10, 0))
    tk.Label(rate_frame, text="Rate £", bg=BG_COLOUR).pack(side="left")
    rate_entry = tk.Entry(rate_frame, width=10)
    rate_entry.pack(side="left")
    tk.Label(rate_frame, text="per night", bg=BG_COLOUR).pack(side="left")

    # builds one row of day / month / year boxes and returns the three entry widgets,
    # so this can be reused for both check-in and check-out without repeating the layout code
    def dateEntryRow(label_text):
        tk.Label(popup, text=label_text, bg=BG_COLOUR).pack(pady=(10, 0))
        frame = tk.Frame(popup, bg=BG_COLOUR)
        frame.pack()
        day = tk.Entry(frame, width=4)
        day.grid(row=0, column=0)
        tk.Label(frame, text="/", bg=BG_COLOUR).grid(row=0, column=1)
        month = tk.Entry(frame, width=4)
        month.grid(row=0, column=2)
        tk.Label(frame, text="/", bg=BG_COLOUR).grid(row=0, column=3)
        year = tk.Entry(frame, width=6)
        year.grid(row=0, column=4)
        return day, month, year

    check_in_day, check_in_month, check_in_year = dateEntryRow("Check in (DD/MM/YYYY)")
    check_out_day, check_out_month, check_out_year = dateEntryRow("Check out (DD/MM/YYYY)")

    # reads three day/month/year boxes and tries to build a real date from them
    # returns (date, None) on success, (None, error message) if the numbers don't form a valid date
    def readDate(day_entry, month_entry, year_entry):
        try:
            day = int(day_entry.get())
            month = int(month_entry.get())
            year = int(year_entry.get())
            return dt.date(year, month, day), None
        except ValueError:
            return None, "that date is invalid"

    button_row = tk.Frame(popup, bg=BG_COLOUR)
    button_row.pack(pady=20)

    def onCancelClicked():
        popup.destroy()

    def onSaveClicked():
        guest = name_entry.get()
        if guest == "":
            messagebox.showerror("Error", "Enter a guest name")
            return

        address = address_entry.get()
        if address == "":
            messagebox.showerror("Error", "Enter an address")
            return

        try:
            rate = int(rate_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Rate must be a number")
            return

        check_in_date, error = readDate(check_in_day, check_in_month, check_in_year)
        if error is not None:
            messagebox.showerror("Error", "Check-in: " + error)
            return

        check_out_date, error = readDate(check_out_day, check_out_month, check_out_year)
        if error is not None:
            messagebox.showerror("Error", "Check-out: " + error)
            return

        if check_in_date < dt.date.today():
            messagebox.showerror("Error", "Check-in cannot be before today")
            return

        if check_out_date <= check_in_date:
            messagebox.showerror("Error", "Check-out must be after check-in")
            return

        nights = (check_out_date - check_in_date).days
        total_fee = nights * rate

        success, message, booking_id = current_property.saveBooking(
            guest, address, check_in_date, check_out_date, rate, total_fee
        )
        if not success:
            messagebox.showerror("Error", message)
            return

        current_property.createInvoice(
            booking_id, guest, address, check_in_date, check_out_date, rate, total_fee
        )
        popup.destroy()
        onBookingSaved()

    tk.Button(
        button_row, text="Cancel", command=onCancelClicked,
        bg="#cccccc", relief="flat", padx=10, pady=5
    ).pack(side="left", padx=10)

    makeButton(button_row, "SAVE", onSaveClicked).pack(side="left", padx=10)

    popup.grab_set()


showPropertyScreen()
root.mainloop()