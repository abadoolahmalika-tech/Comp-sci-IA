import datetime as dt
import sqlite3
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# a property just needs an id (from the database) and a name
class Property:
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

    # grabs every booking for this property, in the order they were added
    def getBookings(self):
        cursor.execute(
            "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ? ORDER BY id",
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
        rows = self.getBookings()
        return [b for b in rows if search.lower() in b[1].lower()]

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

current_property = None

root = tk.Tk()
root.title("Booking System")
root.geometry("520x480")


def clearScreen():
    widget_list = root.winfo_children()
    for widget in widget_list:
        widget.destroy()


# ============================================================
# SCREEN 1: choose a property
# ============================================================

def showPropertyScreen():
    clearScreen()
    global current_property
    current_property = None

    title = tk.Label(root, text="Select a property", font=("Helvetica", 16))
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

    select_button = tk.Button(root, text="Select Property", command=onSelectClicked)
    select_button.pack(pady=5)

    add_label = tk.Label(root, text="Or add a new property:")
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

    add_button = tk.Button(root, text="Add Property", command=onAddClicked)
    add_button.pack(pady=5)


# ============================================================
# SCREEN 2: the main "Bookings" table screen, matching the sketch
# this stays as the main window - Add Booking opens a SEPARATE popup window on top of it
# ============================================================

def showBookingsScreen():
    clearScreen()
    root.title("Bookings - " + current_property.name)

    # ---- top bar: search box ----
    top_frame = tk.Frame(root)
    top_frame.pack(fill="x", padx=10, pady=10)

    tk.Label(top_frame, text="Search:").pack(side="left")
    search_entry = tk.Entry(top_frame)
    search_entry.pack(side="left", fill="x", expand=True, padx=5)

    # ---- the table itself ----
    # ttk.Treeview is tkinter's built-in table widget - columns=(...) names each column,
    # show="headings" hides an extra blank first column it would otherwise add
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

    # keeps track of which database booking id belongs to each row shown in the table,
    # since the table itself only shows the text, not the underlying id
    row_id_lookup = {}

    # (re)loads whichever bookings should currently be shown into the table
    def loadRows(bookings_to_show):
        table.delete(*table.get_children())  # clear every row currently in the table
        row_id_lookup.clear()
        for booking in bookings_to_show:
            booking_id, guest, check_in, check_out, fee = booking
            check_in_str = dt.date.fromisoformat(check_in).strftime("%d/%m/%y")
            check_out_str = dt.date.fromisoformat(check_out).strftime("%d/%m/%y")
            row = table.insert("", tk.END, values=(guest, check_in_str, check_out_str, "£" + str(fee)))
            row_id_lookup[row] = booking_id

    loadRows(current_property.getBookings())

    # runs every time a key is released in the search box - filters the table live
    def onSearchChanged(event):
        search_text = search_entry.get()
        if search_text == "":
            loadRows(current_property.getBookings())
        else:
            loadRows(current_property.searchByName(search_text))

    search_entry.bind("<KeyRelease>", onSearchChanged)

    # ---- bottom bar: action buttons ----
    button_frame = tk.Frame(root)
    button_frame.pack(fill="x", padx=10, pady=10)

    def onAddBookingClicked():
        openAddBookingWindow(onBookingSaved=lambda: loadRows(current_property.getBookings()))

    def onDeleteBookingClicked():
        selected = table.selection()  # this gives back whichever row(s) are highlighted
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

    add_btn = tk.Button(button_frame, text="Add booking", command=onAddBookingClicked)
    add_btn.pack(side="left", padx=5)

    delete_btn = tk.Button(button_frame, text="Delete booking", command=onDeleteBookingClicked)
    delete_btn.pack(side="left", padx=5)

    switch_btn = tk.Button(button_frame, text="Switch property", command=showPropertyScreen)
    switch_btn.pack(side="right", padx=5)


# ============================================================
# the "Add booking" popup window
# this is a Toplevel - a second window that sits on top of the main one
# closing it (the X button, or Cancel) just closes the window, nothing gets saved
# ============================================================

def openAddBookingWindow(onBookingSaved):
    # Toplevel() creates a brand new window, separate from root
    popup = tk.Toplevel(root)
    popup.title("Add booking")
    popup.geometry("300x320")

    tk.Label(popup, text="Name").pack(pady=(15, 0))
    name_entry = tk.Entry(popup)
    name_entry.pack()

    rate_frame = tk.Frame(popup)
    rate_frame.pack(pady=(10, 0))
    tk.Label(rate_frame, text="Rate £").pack(side="left")
    rate_entry = tk.Entry(rate_frame, width=10)
    rate_entry.pack(side="left")
    tk.Label(rate_frame, text="per night").pack(side="left")

    tk.Label(popup, text="Check in (DD/MM/YYYY)").pack(pady=(10, 0))
    check_in_entry = tk.Entry(popup)
    check_in_entry.pack()

    tk.Label(popup, text="Check out (DD/MM/YYYY)").pack(pady=(10, 0))
    check_out_entry = tk.Entry(popup)
    check_out_entry.pack()

    button_row = tk.Frame(popup)
    button_row.pack(pady=20)

    # Cancel just closes this window - nothing gets saved, the main table is untouched
    def onCancelClicked():
        popup.destroy()

    def onSaveClicked():
        guest = name_entry.get()
        if guest == "":
            messagebox.showerror("Error", "Enter a guest name")
            return

        try:
            rate = int(rate_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Rate must be a number")
            return

        try:
            check_in_date = dt.datetime.strptime(check_in_entry.get(), "%d/%m/%Y").date()
        except ValueError:
            messagebox.showerror("Error", "Check-in must be DD/MM/YYYY")
            return

        try:
            check_out_date = dt.datetime.strptime(check_out_entry.get(), "%d/%m/%Y").date()
        except ValueError:
            messagebox.showerror("Error", "Check-out must be DD/MM/YYYY")
            return

        if check_in_date < dt.date.today():
            messagebox.showerror("Error", "Check-in cannot be before today")
            return

        if check_out_date <= check_in_date:
            messagebox.showerror("Error", "Check-out must be after check-in")
            return

        nights = (check_out_date - check_in_date).days
        total_fee = nights * rate

        success, message = current_property.saveBooking(guest, check_in_date, check_out_date, total_fee)
        if not success:
            messagebox.showerror("Error", message)
            return

        current_property.createInvoice(guest, check_in_date, check_out_date, total_fee)
        popup.destroy()          # close the popup now that saving worked
        onBookingSaved()         # tell the main table screen to refresh itself

    cancel_btn = tk.Button(button_row, text="Cancel", command=onCancelClicked)
    cancel_btn.pack(side="left", padx=10)

    save_btn = tk.Button(button_row, text="SAVE", command=onSaveClicked)
    save_btn.pack(side="left", padx=10)

    # this makes the popup "modal" - the main window is blocked from being clicked
    # until this popup is closed, similar to how the sketch shows it sitting on top
    popup.grab_set()


showPropertyScreen()
root.mainloop()