import datetime as dt
import sqlite3
import os
import smtplib
from email.message import EmailMessage
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# colour scheme - change these to change the whole app's look
BG_COLOUR = "#f4f1ec"
ACCENT_COLOUR = "#3f6357"
ACCENT_TEXT_COLOUR = "#ffffff"
TABLE_HEADER_COLOUR = "#e4ded2"


# ---- company info comes from a plain text file, so it can be edited without touching code ----
# expects two lines: company name, then company address
# if the file doesn't exist yet, this creates a placeholder one so the program still runs
def loadCompanyInfo():
    if not os.path.exists("company_info.txt"):
        with open("company_info.txt", "w") as f:
            f.write("Your Company Name\n")
            f.write("123 Example Street, London, UK\n")
    with open("company_info.txt", "r") as f:
        lines = f.readlines()
    name = lines[0].strip() if len(lines) > 0 else "Company Name"
    address = lines[1].strip() if len(lines) > 1 else "Address"
    return name, address


COMPANY_NAME, COMPANY_ADDRESS = loadCompanyInfo()


# ---- email credentials also come from a text file, kept separate and NEVER committed to git ----
# expects four lines: sender email, app password, smtp server, smtp port
# this file should be added to .gitignore - see the note printed below if it's missing
def loadEmailConfig():
    if not os.path.exists("email_config.txt"):
        with open("email_config.txt", "w") as f:
            f.write("your_email@gmail.com\n")
            f.write("your_app_password_here\n")
            f.write("smtp.gmail.com\n")
            f.write("587\n")
        print("Created email_config.txt - fill in your real email details before sending emails.")
        print("Make sure email_config.txt is listed in your .gitignore so it never gets pushed to GitHub.")
    with open("email_config.txt", "r") as f:
        lines = [line.strip() for line in f.readlines()]
    return {
        "address": lines[0],
        "password": lines[1],
        "server": lines[2],
        "port": int(lines[3])
    }


EMAIL_CONFIG = loadEmailConfig()


# sends an email with the invoice pdf attached, using the details from email_config.txt
# returns (True, message) or (False, message) so the gui can show the result
def sendInvoiceEmail(to_address, guest_name, property_name):
    try:
        msg = EmailMessage()
        msg["Subject"] = "Your booking invoice - " + property_name
        msg["From"] = EMAIL_CONFIG["address"]
        msg["To"] = to_address
        msg.set_content(
            "Hi " + guest_name + ",\n\n"
            "Thanks for booking with us. Your invoice is attached.\n\n"
            "Best,\n" + COMPANY_NAME
        )

        with open("invoice.pdf", "rb") as f:
            pdf_data = f.read()
        msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename="invoice.pdf")

        with smtplib.SMTP(EMAIL_CONFIG["server"], EMAIL_CONFIG["port"]) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_CONFIG["address"], EMAIL_CONFIG["password"])
            smtp.send_message(msg)

        return True, "Email sent to " + to_address
    except Exception as error:
        return False, "Could not send email: " + str(error)


class Property:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    def rename(self, new_name):
        cursor.execute("UPDATE properties SET name = ? WHERE id = ?", (new_name, self.id))
        conn.commit()
        self.name = new_name

    # tries to save a new booking. returns (True, message, booking_id) or (False, message, None)
    def saveBooking(self, guest, address, phone, email, check_in_date, check_out_date, rate, fee):
        clash = self._findClash(check_in_date, check_out_date)
        if clash:
            return False, clash, None

        cursor.execute(
            """INSERT INTO bookings (property_id, guest, address, phone, email, check_in, check_out, rate, fee)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.id, guest, address, phone, email, check_in_date.isoformat(), check_out_date.isoformat(), rate, fee)
        )
        conn.commit()
        return True, "booking saved", cursor.lastrowid

    # updates an existing booking's dates/rate, checking for clashes against every OTHER booking
    # (excluding itself, since otherwise it would always "clash" with its own current dates)
    def updateBooking(self, booking_id, check_in_date, check_out_date, rate, fee):
        clash = self._findClash(check_in_date, check_out_date, ignore_booking_id=booking_id)
        if clash:
            return False, clash

        cursor.execute(
            "UPDATE bookings SET check_in = ?, check_out = ?, rate = ?, fee = ? WHERE id = ?",
            (check_in_date.isoformat(), check_out_date.isoformat(), rate, fee, booking_id)
        )
        conn.commit()
        return True, "booking updated"

    # shared clash-checking logic used by both saveBooking and updateBooking
    # a checkout day and a check-in day being the SAME day is allowed (same-day turnover) -
    # only genuine overlap of nights counts as a clash
    def _findClash(self, check_in_date, check_out_date, ignore_booking_id=None):
        cursor.execute(
            "SELECT id, check_in, check_out FROM bookings WHERE property_id = ?",
            (self.id,)
        )
        existing_bookings = cursor.fetchall()

        for booking in existing_bookings:
            existing_id, existing_check_in_str, existing_check_out_str = booking
            if existing_id == ignore_booking_id:
                continue

            existing_check_in = dt.date.fromisoformat(existing_check_in_str)
            existing_check_out = dt.date.fromisoformat(existing_check_out_str)

            # two date ranges DON'T overlap if one ends on or before the other starts -
            # this is what allows one guest's check-out day to be another's check-in day
            no_overlap = existing_check_out <= check_in_date or check_out_date <= existing_check_in
            if not no_overlap:
                return "dates clash with an existing booking (" + existing_check_in.strftime("%d/%m/%Y") + \
                       " - " + existing_check_out.strftime("%d/%m/%Y") + ")"
        return None

    def getBookings(self):
        cursor.execute(
            "SELECT id, guest, address, phone, email, check_in, check_out, rate, fee "
            "FROM bookings WHERE property_id = ? ORDER BY check_in",
            (self.id,)
        )
        return cursor.fetchall()

    def getBookingById(self, booking_id):
        cursor.execute(
            "SELECT id, guest, address, phone, email, check_in, check_out, rate, fee FROM bookings WHERE id = ?",
            (booking_id,)
        )
        return cursor.fetchone()

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

    def searchByName(self, search):
        rows = self.getBookings()
        return [b for b in rows if search.lower() in b[1].lower()]

    # total revenue for this property between two dates (inclusive), based on check-in date
    def revenueBetween(self, start_date, end_date):
        cursor.execute(
            "SELECT check_in, fee FROM bookings WHERE property_id = ?",
            (self.id,)
        )
        rows = cursor.fetchall()
        total = 0
        for check_in_str, fee in rows:
            check_in = dt.date.fromisoformat(check_in_str)
            if start_date <= check_in <= end_date:
                total += fee
        return total

    # revenue broken down by month, between two dates - used for the graph
    def revenueByMonth(self, start_date, end_date):
        cursor.execute(
            "SELECT check_in, fee FROM bookings WHERE property_id = ?",
            (self.id,)
        )
        rows = cursor.fetchall()
        totals_by_month = {}
        for check_in_str, fee in rows:
            check_in = dt.date.fromisoformat(check_in_str)
            if start_date <= check_in <= end_date:
                key = check_in.strftime("%Y-%m")
                totals_by_month[key] = totals_by_month.get(key, 0) + fee
        return totals_by_month

    def createInvoice(self, booking_id, guest, address, check_in_date, check_out_date, rate, fee):
        check_in_str = check_in_date.strftime("%d/%m/%Y")
        check_out_str = check_out_date.strftime("%d/%m/%Y")
        nights = (check_out_date - check_in_date).days

        subtotal = fee
        vat = round(subtotal * 0.2, 2)
        total = round(subtotal + vat, 2)

        c = canvas.Canvas("invoice.pdf", pagesize=letter)
        width, height = letter

        c.setFillColor(colors.HexColor(ACCENT_COLOUR))
        c.rect(0, height - 100, width, 100, fill=True, stroke=False)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(50, height - 65, "INVOICE")

        c.setFont("Helvetica", 10)
        c.drawRightString(width - 50, height - 35, COMPANY_NAME)
        c.drawRightString(width - 50, height - 50, COMPANY_ADDRESS)

        c.setFillColor(colors.black)
        y = height - 130

        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Invoice #" + str(booking_id))
        c.drawRightString(width - 50, y, "Date: " + dt.date.today().strftime("%d/%m/%Y"))
        y -= 30

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

        table_top = y
        row_height = 22

        c.setFillColor(colors.HexColor(TABLE_HEADER_COLOUR))
        c.rect(50, table_top - row_height, width - 100, row_height, fill=True, stroke=False)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(55, table_top - row_height + 6, "Description")
        c.drawString(330, table_top - row_height + 6, "Nights")
        c.drawString(410, table_top - row_height + 6, "Unit Price")
        c.drawRightString(width - 55, table_top - row_height + 6, "Amount")

        y = table_top - row_height
        c.setFont("Helvetica", 10)
        c.drawString(55, y - row_height + 6, "Accommodation (" + self.name + ")")
        c.drawString(330, y - row_height + 6, str(nights))
        c.drawString(410, y - row_height + 6, "£" + str(rate))
        c.drawRightString(width - 55, y - row_height + 6, "£" + str(subtotal))
        y -= row_height

        c.setLineWidth(0.5)
        c.line(50, y, width - 50, y)
        y -= 25

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
        phone TEXT,
        email TEXT,
        check_in TEXT,
        check_out TEXT,
        rate REAL,
        fee REAL
    )
""")
conn.commit()

# these columns are new - if bookings.db already existed from an earlier version, these lines
# add the missing columns in. on a brand new database they're already there, so the try/except
# just quietly does nothing
for column, col_type in [("address", "TEXT"), ("phone", "TEXT"), ("email", "TEXT"), ("rate", "REAL")]:
    try:
        cursor.execute(f"ALTER TABLE bookings ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass
conn.commit()

current_property = None

root = tk.Tk()
root.title("Booking System")
root.geometry("650x600")
root.configure(bg=BG_COLOUR)

style = ttk.Style()
style.theme_use("default")
style.configure("Treeview", background="white", fieldbackground="white", rowheight=26, font=("Helvetica", 10))
style.configure("Treeview.Heading", background=TABLE_HEADER_COLOUR, font=("Helvetica", 10, "bold"))
style.map("Treeview", background=[("selected", ACCENT_COLOUR)], foreground=[("selected", "white")])


def clearScreen():
    for widget in root.winfo_children():
        widget.destroy()


def makeButton(parent, text, command):
    return tk.Button(
        parent, text=text, command=command,
        bg=ACCENT_COLOUR, fg=ACCENT_TEXT_COLOUR,
        activebackground=ACCENT_COLOUR, activeforeground=ACCENT_TEXT_COLOUR,
        font=("Helvetica", 10, "bold"), relief="flat", padx=10, pady=5
    )


# builds a day / month / year row of boxes, used on several screens
def dateEntryRow(parent, label_text):
    tk.Label(parent, text=label_text, bg=BG_COLOUR).pack(pady=(10, 0))
    frame = tk.Frame(parent, bg=BG_COLOUR)
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


def readDate(day_entry, month_entry, year_entry):
    try:
        day = int(day_entry.get())
        month = int(month_entry.get())
        year = int(year_entry.get())
        return dt.date(year, month, day), None
    except ValueError:
        return None, "that date is invalid"


# ============================================================
# SCREEN 1: choose / add / rename / delete a property
# ============================================================

def showPropertyScreen():
    clearScreen()
    global current_property
    current_property = None

    tk.Label(root, text="Select a property", font=("Helvetica", 16, "bold"), bg=BG_COLOUR).pack(pady=10)

    property_listbox = tk.Listbox(root, width=40)
    property_listbox.pack(pady=10)

    cursor.execute("SELECT id, name FROM properties")
    property_rows = cursor.fetchall()
    for row in property_rows:
        property_listbox.insert(tk.END, row[1])

    def getSelectedRow():
        selected_index = property_listbox.curselection()
        if not selected_index:
            messagebox.showerror("Error", "Click a property first")
            return None
        return property_rows[selected_index[0]]

    def onSelectClicked():
        row = getSelectedRow()
        if row is None:
            return
        global current_property
        current_property = Property(row[0], row[1])
        showBookingsScreen()

    def onRenameClicked():
        row = getSelectedRow()
        if row is None:
            return
        prop = Property(row[0], row[1])
        renamePropertyDialog(prop)

    def onDeleteClicked():
        row = getSelectedRow()
        if row is None:
            return
        prop_id, prop_name = row
        cursor.execute("SELECT COUNT(*) FROM bookings WHERE property_id = ?", (prop_id,))
        booking_count = cursor.fetchone()[0]

        confirm_message = "Delete '" + prop_name + "'?"
        if booking_count > 0:
            confirm_message += "\n\nThis will also delete its " + str(booking_count) + " booking(s)."

        if messagebox.askyesno("Confirm delete", confirm_message):
            cursor.execute("DELETE FROM bookings WHERE property_id = ?", (prop_id,))
            cursor.execute("DELETE FROM properties WHERE id = ?", (prop_id,))
            conn.commit()
            showPropertyScreen()

    button_row = tk.Frame(root, bg=BG_COLOUR)
    button_row.pack(pady=5)
    makeButton(button_row, "Select", onSelectClicked).pack(side="left", padx=3)
    makeButton(button_row, "Rename", onRenameClicked).pack(side="left", padx=3)
    tk.Button(
        button_row, text="Delete", command=onDeleteClicked,
        bg="#a33d3d", fg="white", relief="flat", padx=10, pady=5, font=("Helvetica", 10, "bold")
    ).pack(side="left", padx=3)

    tk.Label(root, text="Or add a new property:", bg=BG_COLOUR).pack(pady=(20, 0))
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
    makeButton(root, "Performance Report", showPerformanceReportScreen).pack(pady=(20, 5))
    makeButton(root, "Email Settings", showEmailSettingsDialog).pack(pady=5)
    makeButton(root, "Company Settings", showCompanySettingsDialog).pack(pady=5)


def showCompanySettingsDialog():
    popup = tk.Toplevel(root)
    popup.title("Company Settings")
    popup.geometry("340x220")
    popup.configure(bg=BG_COLOUR)

    tk.Label(popup, text="Company name:", bg=BG_COLOUR).pack(pady=(15, 0))
    name_entry = tk.Entry(popup, width=35)
    name_entry.insert(0, COMPANY_NAME)
    name_entry.pack()

    tk.Label(popup, text="Company address:", bg=BG_COLOUR).pack(pady=(10, 0))
    address_entry = tk.Entry(popup, width=35)
    address_entry.insert(0, COMPANY_ADDRESS)
    address_entry.pack()

    def onSaveClicked():
        # COMPANY_NAME and COMPANY_ADDRESS are plain variables (not a dictionary like EMAIL_CONFIG),
        # so "global" is needed here to say we're changing the actual module-level variable,
        # not just creating a new local one that disappears once this function ends
        global COMPANY_NAME, COMPANY_ADDRESS
        COMPANY_NAME = name_entry.get()
        COMPANY_ADDRESS = address_entry.get()

        with open("company_info.txt", "w") as f:
            f.write(COMPANY_NAME + "\n")
            f.write(COMPANY_ADDRESS + "\n")

        messagebox.showinfo("Saved", "Company details updated")
        popup.destroy()

    makeButton(popup, "Save", onSaveClicked).pack(pady=20)
    popup.grab_set()


def showEmailSettingsDialog():
    popup = tk.Toplevel(root)
    popup.title("Email Settings")
    popup.geometry("340x320")
    popup.configure(bg=BG_COLOUR)

    tk.Label(popup, text="Sender email address:", bg=BG_COLOUR).pack(pady=(15, 0))
    address_entry = tk.Entry(popup, width=35)
    address_entry.insert(0, EMAIL_CONFIG["address"])
    address_entry.pack()

    tk.Label(popup, text="App password:", bg=BG_COLOUR).pack(pady=(10, 0))
    password_entry = tk.Entry(popup, width=35, show="*")  # show="*" hides it like a normal password box
    password_entry.insert(0, EMAIL_CONFIG["password"])
    password_entry.pack()

    tk.Label(popup, text="SMTP server:", bg=BG_COLOUR).pack(pady=(10, 0))
    server_entry = tk.Entry(popup, width=35)
    server_entry.insert(0, EMAIL_CONFIG["server"])
    server_entry.pack()

    tk.Label(popup, text="SMTP port:", bg=BG_COLOUR).pack(pady=(10, 0))
    port_entry = tk.Entry(popup, width=10)
    port_entry.insert(0, str(EMAIL_CONFIG["port"]))
    port_entry.pack()

    note = tk.Label(
        popup,
        text="For Gmail, this needs an\n\"app password\", not your normal password.",
        bg=BG_COLOUR, fg="#777777", font=("Helvetica", 8)
    )
    note.pack(pady=(10, 0))

    def onSaveClicked():
        address = address_entry.get()
        password = password_entry.get()
        server = server_entry.get()
        try:
            port = int(port_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Port must be a number")
            return

        # update the dictionary in place, rather than replacing it, so every part of the
        # program that already has a reference to EMAIL_CONFIG sees the new values too
        EMAIL_CONFIG["address"] = address
        EMAIL_CONFIG["password"] = password
        EMAIL_CONFIG["server"] = server
        EMAIL_CONFIG["port"] = port

        with open("email_config.txt", "w") as f:
            f.write(address + "\n")
            f.write(password + "\n")
            f.write(server + "\n")
            f.write(str(port) + "\n")

        messagebox.showinfo("Saved", "Email settings updated")
        popup.destroy()

    makeButton(popup, "Save", onSaveClicked).pack(pady=20)
    popup.grab_set()


def renamePropertyDialog(prop):
    popup = tk.Toplevel(root)
    popup.title("Rename property")
    popup.configure(bg=BG_COLOUR)
    popup.geometry("300x150")

    tk.Label(popup, text="New name:", bg=BG_COLOUR).pack(pady=(20, 5))
    name_entry = tk.Entry(popup)
    name_entry.insert(0, prop.name)
    name_entry.pack()

    def onSaveClicked():
        new_name = name_entry.get()
        if new_name == "":
            messagebox.showerror("Error", "Enter a name")
            return
        prop.rename(new_name)
        popup.destroy()
        showPropertyScreen()

    makeButton(popup, "Save", onSaveClicked).pack(pady=20)
    popup.grab_set()


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
            booking_id, guest, address, phone, email, check_in, check_out, rate, fee = booking
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

    def getSelectedBookingId():
        selected = table.selection()
        if not selected:
            messagebox.showerror("Error", "Click a booking in the table first")
            return None
        return row_id_lookup[selected[0]]

    def onAddBookingClicked():
        openBookingForm(mode="add", booking_id=None, onDone=lambda: loadRows(current_property.getBookings()))

    def onEditBookingClicked():
        booking_id = getSelectedBookingId()
        if booking_id is None:
            return
        openBookingForm(mode="edit", booking_id=booking_id, onDone=lambda: loadRows(current_property.getBookings()))

    def onDeleteBookingClicked():
        booking_id = getSelectedBookingId()
        if booking_id is None:
            return
        success, message = current_property.deleteBookingById(booking_id)
        if not success:
            messagebox.showerror("Error", message)
        else:
            loadRows(current_property.getBookings())

    def onEmailInvoiceClicked():
        booking_id = getSelectedBookingId()
        if booking_id is None:
            return
        booking = current_property.getBookingById(booking_id)
        _, guest, address, phone, email, check_in, check_out, rate, fee = booking
        if not email:
            messagebox.showerror("Error", "This booking has no email address on file")
            return

        check_in_date = dt.date.fromisoformat(check_in)
        check_out_date = dt.date.fromisoformat(check_out)
        current_property.createInvoice(booking_id, guest, address, check_in_date, check_out_date, rate, fee)

        success, message = sendInvoiceEmail(email, guest, current_property.name)
        if success:
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Error", message)

    def onViewDetailsClicked():
        booking_id = getSelectedBookingId()
        if booking_id is None:
            return
        booking = current_property.getBookingById(booking_id)
        showBookingDetailsPopup(booking)

    button_frame = tk.Frame(root, bg=BG_COLOUR)
    button_frame.pack(fill="x", padx=10, pady=10)
    makeButton(button_frame, "Add booking", onAddBookingClicked).pack(side="left", padx=3)
    makeButton(button_frame, "Edit booking", onEditBookingClicked).pack(side="left", padx=3)
    makeButton(button_frame, "Delete booking", onDeleteBookingClicked).pack(side="left", padx=3)
    makeButton(button_frame, "View details", onViewDetailsClicked).pack(side="left", padx=3)
    makeButton(button_frame, "Email invoice", onEmailInvoiceClicked).pack(side="left", padx=3)
    makeButton(button_frame, "Switch property", showPropertyScreen).pack(side="right", padx=3)


# small popup showing everything on file for one booking - name, address, phone, email, dates, cost
def showBookingDetailsPopup(booking):
    booking_id, guest, address, phone, email, check_in, check_out, rate, fee = booking
    check_in_str = dt.date.fromisoformat(check_in).strftime("%d/%m/%Y")
    check_out_str = dt.date.fromisoformat(check_out).strftime("%d/%m/%Y")

    popup = tk.Toplevel(root)
    popup.title("Booking Details")
    popup.geometry("320x300")
    popup.configure(bg=BG_COLOUR)

    # each row is just a label pair - a bold field name on the left, the value on the right
    def detailRow(field_name, value):
        row = tk.Frame(popup, bg=BG_COLOUR)
        row.pack(fill="x", padx=20, pady=4)
        tk.Label(row, text=field_name + ":", bg=BG_COLOUR, font=("Helvetica", 10, "bold"), width=10, anchor="w").pack(side="left")
        tk.Label(row, text=value if value else "-", bg=BG_COLOUR, anchor="w").pack(side="left")

    tk.Label(popup, text="Booking #" + str(booking_id), bg=BG_COLOUR, font=("Helvetica", 14, "bold")).pack(pady=(15, 10))

    detailRow("Name", guest)
    detailRow("Address", address)
    detailRow("Phone", phone)
    detailRow("Email", email)
    detailRow("Check-in", check_in_str)
    detailRow("Check-out", check_out_str)
    detailRow("Rate", "£" + str(rate) + "/night")
    detailRow("Total", "£" + str(fee))

    makeButton(popup, "Close", popup.destroy).pack(pady=20)


# ============================================================
# add / edit booking popup (shared form for both, since they need the same fields)
# ============================================================

def openBookingForm(mode, booking_id, onDone):
    popup = tk.Toplevel(root)
    popup.title("Add booking" if mode == "add" else "Edit booking")
    popup.geometry("340x560")
    popup.configure(bg=BG_COLOUR)

    existing = current_property.getBookingById(booking_id) if mode == "edit" else None

    tk.Label(popup, text="Name", bg=BG_COLOUR).pack(pady=(15, 0))
    name_entry = tk.Entry(popup)
    name_entry.pack()

    tk.Label(popup, text="Address", bg=BG_COLOUR).pack(pady=(10, 0))
    address_entry = tk.Entry(popup, width=35)
    address_entry.pack()

    tk.Label(popup, text="Phone", bg=BG_COLOUR).pack(pady=(10, 0))
    phone_entry = tk.Entry(popup)
    phone_entry.pack()

    tk.Label(popup, text="Email", bg=BG_COLOUR).pack(pady=(10, 0))
    email_entry = tk.Entry(popup)
    email_entry.pack()

    rate_frame = tk.Frame(popup, bg=BG_COLOUR)
    rate_frame.pack(pady=(10, 0))
    tk.Label(rate_frame, text="Rate £", bg=BG_COLOUR).pack(side="left")
    rate_entry = tk.Entry(rate_frame, width=10)
    rate_entry.pack(side="left")
    tk.Label(rate_frame, text="per night", bg=BG_COLOUR).pack(side="left")

    check_in_day, check_in_month, check_in_year = dateEntryRow(popup, "Check in (DD/MM/YYYY)")
    check_out_day, check_out_month, check_out_year = dateEntryRow(popup, "Check out (DD/MM/YYYY)")

    # editing a booking pre-fills every field with its current values, and locks the
    # guest/address/phone/email fields since those aren't part of what's being changed here
    if mode == "edit":
        _, guest, address, phone, email, check_in, check_out, rate, fee = existing
        name_entry.insert(0, guest)
        address_entry.insert(0, address or "")
        phone_entry.insert(0, phone or "")
        email_entry.insert(0, email or "")
        rate_entry.insert(0, str(rate))
        for entry in (name_entry, address_entry, phone_entry, email_entry):
            entry.config(state="disabled")

        check_in_date = dt.date.fromisoformat(check_in)
        check_out_date = dt.date.fromisoformat(check_out)
        check_in_day.insert(0, check_in_date.day)
        check_in_month.insert(0, check_in_date.month)
        check_in_year.insert(0, check_in_date.year)
        check_out_day.insert(0, check_out_date.day)
        check_out_month.insert(0, check_out_date.month)
        check_out_year.insert(0, check_out_date.year)

    button_row = tk.Frame(popup, bg=BG_COLOUR)
    button_row.pack(pady=20)

    def onCancelClicked():
        popup.destroy()

    def onSaveClicked():
        check_in_date, error = readDate(check_in_day, check_in_month, check_in_year)
        if error is not None:
            messagebox.showerror("Error", "Check-in: " + error)
            return

        check_out_date, error = readDate(check_out_day, check_out_month, check_out_year)
        if error is not None:
            messagebox.showerror("Error", "Check-out: " + error)
            return

        if check_out_date <= check_in_date:
            messagebox.showerror("Error", "Check-out must be after check-in")
            return

        try:
            rate = int(rate_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Rate must be a number")
            return

        nights = (check_out_date - check_in_date).days
        total_fee = nights * rate

        if mode == "add":
            guest = name_entry.get()
            if guest == "":
                messagebox.showerror("Error", "Enter a guest name")
                return
            address = address_entry.get()
            phone = phone_entry.get()
            email = email_entry.get()

            if check_in_date < dt.date.today():
                messagebox.showerror("Error", "Check-in cannot be before today")
                return

            success, message, new_booking_id = current_property.saveBooking(
                guest, address, phone, email, check_in_date, check_out_date, rate, total_fee
            )
            if not success:
                messagebox.showerror("Error", message)
                return

            current_property.createInvoice(new_booking_id, guest, address, check_in_date, check_out_date, rate, total_fee)
            messagebox.showinfo("Success", "Booking created. Invoice saved as invoice.pdf")
        else:
            success, message = current_property.updateBooking(booking_id, check_in_date, check_out_date, rate, total_fee)
            if not success:
                messagebox.showerror("Error", message)
                return
            messagebox.showinfo("Success", "Booking updated")

        popup.destroy()
        onDone()

    tk.Button(
        button_row, text="Cancel", command=onCancelClicked,
        bg="#cccccc", relief="flat", padx=10, pady=5
    ).pack(side="left", padx=10)
    makeButton(button_row, "SAVE", onSaveClicked).pack(side="left", padx=10)

    popup.grab_set()


# ============================================================
# performance report screen - pick properties + a date range, see total revenue and a graph
# ============================================================

def showPerformanceReportScreen():
    clearScreen()
    tk.Label(root, text="Performance Report", font=("Helvetica", 16, "bold"), bg=BG_COLOUR).pack(pady=10)

    tk.Label(root, text="Select properties (ctrl+click for more than one):", bg=BG_COLOUR).pack()
    property_listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, width=40, height=6)
    property_listbox.pack(pady=5)

    cursor.execute("SELECT id, name FROM properties")
    property_rows = cursor.fetchall()
    for row in property_rows:
        property_listbox.insert(tk.END, row[1])
    property_listbox.select_set(0, tk.END)  # everything selected by default

    date_frame = tk.Frame(root, bg=BG_COLOUR)
    date_frame.pack(pady=5)

    left_col = tk.Frame(date_frame, bg=BG_COLOUR)
    left_col.pack(side="left", padx=20)
    start_day, start_month, start_year = dateEntryRow(left_col, "From:")

    right_col = tk.Frame(date_frame, bg=BG_COLOUR)
    right_col.pack(side="left", padx=20)
    end_day, end_month, end_year = dateEntryRow(right_col, "To:")

    # fills the from/to boxes with a given pair of dates - used by the quick-pick buttons below
    def setDateBoxes(day_box, month_box, year_box, date_value):
        day_box.delete(0, tk.END)
        day_box.insert(0, date_value.day)
        month_box.delete(0, tk.END)
        month_box.insert(0, date_value.month)
        year_box.delete(0, tk.END)
        year_box.insert(0, date_value.year)

    # sets both from/to boxes based on how far back to go, then runs the report straight away
    def quickRange(days_back=None, all_time=False):
        today = dt.date.today()
        if all_time:
            start_date = dt.date(2000, 1, 1)  # far enough back to include everything realistic
        else:
            start_date = today - dt.timedelta(days=days_back)
        setDateBoxes(start_day, start_month, start_year, start_date)
        setDateBoxes(end_day, end_month, end_year, today)
        onGenerateClicked()

    quick_button_row = tk.Frame(root, bg=BG_COLOUR)
    quick_button_row.pack(pady=5)
    tk.Button(quick_button_row, text="Last Week", command=lambda: quickRange(days_back=7)).pack(side="left", padx=3)
    tk.Button(quick_button_row, text="Last Month", command=lambda: quickRange(days_back=30)).pack(side="left", padx=3)
    tk.Button(quick_button_row, text="Last Year", command=lambda: quickRange(days_back=365)).pack(side="left", padx=3)
    tk.Button(quick_button_row, text="All Time", command=lambda: quickRange(all_time=True)).pack(side="left", padx=3)

    result_label = tk.Label(root, text="", bg=BG_COLOUR, font=("Helvetica", 12, "bold"))
    result_label.pack(pady=10)

    graph_frame = tk.Frame(root, bg=BG_COLOUR)
    graph_frame.pack(fill="both", expand=True, padx=10)

    def onGenerateClicked():
        for widget in graph_frame.winfo_children():
            widget.destroy()

        selected_indexes = property_listbox.curselection()
        if not selected_indexes:
            messagebox.showerror("Error", "Select at least one property")
            return

        start_date, error = readDate(start_day, start_month, start_year)
        if error is not None:
            messagebox.showerror("Error", "From date: " + error)
            return
        end_date, error = readDate(end_day, end_month, end_year)
        if error is not None:
            messagebox.showerror("Error", "To date: " + error)
            return

        selected_properties = [Property(property_rows[i][0], property_rows[i][1]) for i in selected_indexes]

        total_revenue = 0
        combined_months = {}
        for prop in selected_properties:
            total_revenue += prop.revenueBetween(start_date, end_date)
            monthly = prop.revenueByMonth(start_date, end_date)
            for month, amount in monthly.items():
                combined_months[month] = combined_months.get(month, 0) + amount

        result_label.config(text="Total revenue: £" + str(total_revenue))

        sorted_months = sorted(combined_months.keys())
        values = [combined_months[m] for m in sorted_months]

        figure = Figure(figsize=(5, 3), dpi=100)
        plot = figure.add_subplot(111)
        plot.plot(sorted_months, values, marker="o", color=ACCENT_COLOUR)
        plot.set_title("Revenue by month")
        plot.set_ylabel("£")
        figure.autofmt_xdate(rotation=45)

        canvas_widget = FigureCanvasTkAgg(figure, master=graph_frame)
        canvas_widget.draw()
        canvas_widget.get_tk_widget().pack(fill="both", expand=True)

    makeButton(root, "Generate Report", onGenerateClicked).pack(pady=5)
    makeButton(root, "Back", showPropertyScreen).pack(pady=5)


showPropertyScreen()
root.mainloop()