import datetime as dt
import sqlite3
import tkinter as tk
from tkinter import messagebox
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


class Property:
    # a property just needs an id (from the database) and a name
    def __init__(self, id, name):
        self.id = id
        self.name = name

    # tries to save a new booking for this property
    # returns (True, message) if it worked, (False, message) if it clashed with an existing booking
    def saveBooking(self, guest, check_in_date, check_out_date, fee):
        cursor.execute(
            "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ?",
            (self.id,)
        )
        existing_bookings = cursor.fetchall()

        # check the new dates against every existing booking for this property
        for booking in existing_bookings:
            booking_check_in = dt.date.fromisoformat(booking[2])
            booking_check_out = dt.date.fromisoformat(booking[3])
            if booking_check_in <= check_in_date <= booking_check_out:
                return False, "dates taken (check-in falls inside an existing booking)"
            elif booking_check_in <= check_out_date <= booking_check_out:
                return False, "dates taken (check-out falls inside an existing booking)"
            elif check_in_date <= booking_check_in and booking_check_out <= check_out_date:
                return False, "dates taken (an existing booking lies inside your chosen dates)"

        # no clashes, so save it. dates get stored as YYYY-MM-DD strings so they sort properly
        cursor.execute(
            "INSERT INTO bookings (property_id, guest, check_in, check_out, fee) VALUES (?, ?, ?, ?, ?)",
            (self.id, guest, check_in_date.isoformat(), check_out_date.isoformat(), fee)
        )
        conn.commit()
        return True, "booking saved"

    # grabs all bookings for this property, sorted however you want
    # sortingby: 0 = booking id (order added), 1 = check-in date, 2 = check-out date
    def sortBookings(self, sortingby, reverse=False):
        columns = {0: "id", 1: "check_in", 2: "check_out"}
        column = columns[sortingby]
        order = "DESC" if reverse else "ASC"
        cursor.execute(
            f"SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ? ORDER BY {column} {order}",
            (self.id,)
        )
        return cursor.fetchall()

    # deletes one booking by its database id
    # blocks deleting anything that's already happened, so past bookings stay as a record
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

    # case-insensitive "contains" search on guest name, e.g. "ali" matches "Alice"
    def searchByName(self, search):
        cursor.execute(
            "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ?",
            (self.id,)
        )
        rows = cursor.fetchall()
        return [b for b in rows if search.lower() in b[1].lower()]

    # finds bookings where the given date falls somewhere between check-in and check-out
    def searchByDate(self, search_date):
        cursor.execute(
            "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ?",
            (self.id,)
        )
        rows = cursor.fetchall()
        matches = []
        for booking in rows:
            booking_check_in = dt.date.fromisoformat(booking[2])
            booking_check_out = dt.date.fromisoformat(booking[3])
            if booking_check_in <= search_date <= booking_check_out:
                matches.append(booking)
        return matches

    # spits out a simple pdf invoice for a booking using reportlab
    def createInvoice(self, guest, check_in_date, check_out_date, fee):
        check_in_str = check_in_date.strftime("%d/%m/%Y")
        check_out_str = check_out_date.strftime("%d/%m/%Y")
        fee_str = str(fee)

        c = canvas.Canvas("invoice.pdf", pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 24)
        c.drawString(50, height - 80, "Invoice")

        c.setLineWidth(1)
        c.line(50, height - 90, width - 50, height - 90)

        c.setFont("Helvetica", 12)
        y = height - 130
        line_gap = 25

        # just stepping y down a fixed gap after each line so everything's evenly spaced
        c.drawString(50, y, "Property: " + self.name)
        y -= line_gap
        c.drawString(50, y, "Guest: " + guest)
        y -= line_gap
        c.drawString(50, y, "Check-in: " + check_in_str)
        y -= line_gap
        c.drawString(50, y, "Check-out: " + check_out_str)
        y -= line_gap

        c.line(50, y, width - 50, y)
        y -= line_gap

        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Total Fee: £" + fee_str)

        c.save()


# set up the database connection once, right at the start, so every function can use it
conn = sqlite3.connect("bookings.db")
cursor = conn.cursor()

# "if not exists" means this only actually creates the tables the very first time the program runs
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
        check_in TEXT,
        check_out TEXT,
        fee REAL
    )
""")
conn.commit()

# keeps track of whichever property is currently selected
current_property = None

root = tk.Tk()
root.title("Booking System")
root.geometry("550x550")


# wipes every widget off the window so the next screen can be drawn fresh
# this is basically how "switching screens" works in tkinter, since there's no built-in concept of pages
def clearScreen():
    for widget in root.winfo_children():
        widget.destroy()


# turns one booking row from the database into a readable line of text
def formatRow(booking):
    booking_id, guest, check_in, check_out, fee = booking
    check_in_str = dt.date.fromisoformat(check_in).strftime("%d/%m/%Y")
    check_out_str = dt.date.fromisoformat(check_out).strftime("%d/%m/%Y")
    return guest + "  |  " + check_in_str + " - " + check_out_str + "  |  £" + str(fee)


# ---------- property selection screen ----------
# first thing you see when the app opens, or when you switch properties

def showPropertyScreen():
    clearScreen()
    global current_property
    current_property = None

    tk.Label(root, text="Select a property", font=("Helvetica", 16)).pack(pady=10)

    cursor.execute("SELECT id, name FROM properties")
    rows = cursor.fetchall()

    # one button per property, however many there are
    # the pid=prop_id, pname=name bit locks in the value for each button at creation time,
    # otherwise every button would end up using whatever the last property in the loop was
    for row in rows:
        prop_id, name = row
        tk.Button(
            root, text=name, width=30,
            command=lambda pid=prop_id, pname=name: selectProperty(pid, pname)
        ).pack(pady=3)

    tk.Label(root, text="Add a new property:").pack(pady=(20, 0))
    name_entry = tk.Entry(root)
    name_entry.pack()

    def addProperty():
        name = name_entry.get()
        if name == "":
            messagebox.showerror("Error", "Enter a property name")
            return
        cursor.execute("INSERT INTO properties (name) VALUES (?)", (name,))
        conn.commit()
        showPropertyScreen()  # refresh so the new property shows up in the list

    tk.Button(root, text="Add Property", command=addProperty).pack(pady=5)


def selectProperty(prop_id, name):
    global current_property
    current_property = Property(prop_id, name)
    showMainMenu()


# ---------- main menu screen ----------
# shows once a property's picked, has buttons for everything else

def showMainMenu():
    clearScreen()
    tk.Label(root, text=current_property.name, font=("Helvetica", 16)).pack(pady=10)

    tk.Button(root, text="Create Booking", width=25, command=showCreateBookingScreen).pack(pady=5)
    tk.Button(root, text="View Bookings", width=25, command=lambda: showViewBookingsScreen()).pack(pady=5)
    tk.Button(root, text="Search by Name", width=25, command=showSearchByNameScreen).pack(pady=5)
    tk.Button(root, text="Search by Date", width=25, command=showSearchByDateScreen).pack(pady=5)
    tk.Button(root, text="Switch Property", width=25, command=showPropertyScreen).pack(pady=(20, 5))


# ---------- shared helpers for date input ----------
# used by both the create booking screen and the search by date screen

# builds a day / month / year row of little text boxes and returns the three entry widgets
def dateEntryRow(label_text):
    tk.Label(root, text=label_text).pack()
    frame = tk.Frame(root)
    frame.pack()
    day = tk.Entry(frame, width=4)
    day.grid(row=0, column=0)
    tk.Label(frame, text="/").grid(row=0, column=1)
    month = tk.Entry(frame, width=4)
    month.grid(row=0, column=2)
    tk.Label(frame, text="/").grid(row=0, column=3)
    year = tk.Entry(frame, width=6)
    year.grid(row=0, column=4)
    return day, month, year


# reads the three boxes and tries to turn them into a real date
# returns (date, None) if it works, (None, error message) if it doesn't
def readDate(day_entry, month_entry, year_entry):
    try:
        day = int(day_entry.get())
        month = int(month_entry.get())
        year = int(year_entry.get())
        return dt.date(year, month, day), None
    except ValueError:
        return None, "that date is invalid"


# ---------- create booking screen ----------

def showCreateBookingScreen():
    clearScreen()
    tk.Label(root, text="Create Booking - " + current_property.name, font=("Helvetica", 16)).pack(pady=10)

    tk.Label(root, text="Guest name:").pack()
    guest_entry = tk.Entry(root)
    guest_entry.pack()

    tk.Label(root, text="Nightly rate (£):").pack()
    rate_entry = tk.Entry(root)
    rate_entry.pack()

    check_in_day, check_in_month, check_in_year = dateEntryRow("Check-in date:")
    check_out_day, check_out_month, check_out_year = dateEntryRow("Check-out date:")

    # runs when the "create booking" button is clicked, checks everything before saving
    def submitBooking():
        guest = guest_entry.get()
        if guest == "":
            messagebox.showerror("Error", "Enter a guest name")
            return

        try:
            rate = int(rate_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Rate must be a number")
            return

        check_in_date, error = readDate(check_in_day, check_in_month, check_in_year)
        if error:
            messagebox.showerror("Error", "Check-in: " + error)
            return

        check_out_date, error = readDate(check_out_day, check_out_month, check_out_year)
        if error:
            messagebox.showerror("Error", "Check-out: " + error)
            return

        if check_in_date < dt.date.today():
            messagebox.showerror("Error", "Check-in cannot be before today")
            return
        if check_out_date <= check_in_date:
            messagebox.showerror("Error", "Check-out must be after check-in")
            return

        total_fee = (check_out_date - check_in_date).days * rate
        success, message = current_property.saveBooking(guest, check_in_date, check_out_date, total_fee)

        if not success:
            messagebox.showerror("Error", message)
            return

        current_property.createInvoice(guest, check_in_date, check_out_date, total_fee)
        messagebox.showinfo("Success", "Booking created. Invoice saved as invoice.pdf")
        showMainMenu()

    tk.Button(root, text="Create Booking", command=submitBooking).pack(pady=10)
    tk.Button(root, text="Back", command=showMainMenu).pack()


# ---------- view bookings screen ----------
# sortby/reverse get passed back into itself when you click a sort button, so the screen
# just redraws itself with the new order applied

def showViewBookingsScreen(sortby=0, reverse=False):
    clearScreen()
    tk.Label(root, text="Bookings - " + current_property.name, font=("Helvetica", 16)).pack(pady=10)

    sort_frame = tk.Frame(root)
    sort_frame.pack(pady=5)
    tk.Label(sort_frame, text="Sort by:").pack(side="left")
    tk.Button(sort_frame, text="Check-in", command=lambda: showViewBookingsScreen(1, False)).pack(side="left")
    tk.Button(sort_frame, text="Check-out", command=lambda: showViewBookingsScreen(2, False)).pack(side="left")
    tk.Button(sort_frame, text="Reverse", command=lambda: showViewBookingsScreen(sortby, not reverse)).pack(side="left")

    bookings = current_property.sortBookings(sortby, reverse)

    frame = tk.Frame(root)
    frame.pack(pady=10, fill="both", expand=True)

    if not bookings:
        tk.Label(frame, text="No bookings yet").pack()

    for booking in bookings:
        booking_id = booking[0]
        row = tk.Frame(frame)
        row.pack(fill="x", pady=2)

        tk.Label(row, text=formatRow(booking), anchor="w").pack(side="left")

        # same trick as the property buttons - locks in bid to this specific booking's id,
        # otherwise every delete button would end up deleting the last booking in the loop
        def makeDeleteHandler(bid=booking_id):
            def handler():
                success, message = current_property.deleteBookingById(bid)
                if not success:
                    messagebox.showerror("Error", message)
                else:
                    showViewBookingsScreen(sortby, reverse)  # refresh with the same sort still applied
            return handler

        tk.Button(row, text="Delete", command=makeDeleteHandler()).pack(side="right")

    tk.Button(root, text="Back", command=showMainMenu).pack(pady=10)


# ---------- search by name screen ----------

def showSearchByNameScreen():
    clearScreen()
    tk.Label(root, text="Search by Name", font=("Helvetica", 16)).pack(pady=10)

    search_entry = tk.Entry(root)
    search_entry.pack(pady=5)

    results_frame = tk.Frame(root)
    results_frame.pack(pady=10, fill="both", expand=True)

    def runSearch():
        # clear out any results from the last search before showing new ones
        for widget in results_frame.winfo_children():
            widget.destroy()

        matches = current_property.searchByName(search_entry.get())

        if not matches:
            tk.Label(results_frame, text="No bookings found for that name").pack()
        for booking in matches:
            tk.Label(results_frame, text=formatRow(booking), anchor="w").pack(fill="x")

    tk.Button(root, text="Search", command=runSearch).pack()
    tk.Button(root, text="Back", command=showMainMenu).pack(pady=10)


# ---------- search by date screen ----------

def showSearchByDateScreen():
    clearScreen()
    tk.Label(root, text="Search by Date", font=("Helvetica", 16)).pack(pady=10)

    day, month, year = dateEntryRow("Date to search for:")

    results_frame = tk.Frame(root)
    results_frame.pack(pady=10, fill="both", expand=True)

    def runSearch():
        for widget in results_frame.winfo_children():
            widget.destroy()

        search_date, error = readDate(day, month, year)
        if error:
            tk.Label(results_frame, text=error).pack()
            return

        matches = current_property.searchByDate(search_date)

        if not matches:
            tk.Label(results_frame, text="No bookings found for that date").pack()
        for booking in matches:
            tk.Label(results_frame, text=formatRow(booking), anchor="w").pack(fill="x")

    tk.Button(root, text="Search", command=runSearch).pack(pady=5)
    tk.Button(root, text="Back", command=showMainMenu).pack(pady=10)


# kick things off with the property picker, then hand control over to tkinter's event loop
showPropertyScreen()
root.mainloop()