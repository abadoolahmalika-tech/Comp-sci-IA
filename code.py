import datetime as dt
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


class Property:
    def __init__(self, id, name):
        self.id = id
        self.name = name

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


def createProperty():
    name = input("Enter property name: ")
    cursor.execute("INSERT INTO properties (name) VALUES (?)", (name,))
    conn.commit()
    new_id = cursor.lastrowid
    return Property(new_id, name)


def chooseProperty():
    cursor.execute("SELECT id, name FROM properties")
    rows = cursor.fetchall()
    if not rows:
        print("No properties yet — let's create one.")
        return createProperty()

    count = 1
    for row in rows:
        print(str(count) + ") " + row[1])
        count += 1
    print(str(count) + ") Add a new property")

    invalid = True
    while invalid:
        choice = input("Choose a property: ")
        try:
            choice = int(choice)
            if 1 <= choice <= len(rows):
                row = rows[choice - 1]
                return Property(row[0], row[1])
            elif choice == len(rows) + 1:
                return createProperty()
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid (Value error)")

    count = 1
    for row in rows:
        print(str(count) + ") " + row[1] + " (£" + str(row[2]) + "/night)")
        count += 1
    print(str(count) + ") Add a new property")

    invalid = True
    while invalid:
        choice = input("Choose a property: ")
        try:
            choice = int(choice)
            if 1 <= choice <= len(rows):
                row = rows[choice - 1]
                return Property(row[0], row[1], row[2])
            elif choice == len(rows) + 1:
                return createProperty()
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid (Value error)")


def saveBooking(property, Pguest, Pcheck_in_date, Pcheck_out_date, Pfee):
    clashed = False
    cursor.execute("SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ?", (property.id,))
    existing_bookings = cursor.fetchall()

    for booking in existing_bookings:
        booking_check_in = dt.date.fromisoformat(booking[2])
        booking_check_out = dt.date.fromisoformat(booking[3])
        if booking_check_in <= Pcheck_in_date <= booking_check_out:
            print("dates taken (check in between existing booking)")
            clashed = True
        elif booking_check_in <= Pcheck_out_date <= booking_check_out:
            print("dates taken (checkout between existing booking)")
            clashed = True
        elif Pcheck_in_date <= booking_check_in and booking_check_out <= Pcheck_out_date:
            print("dates taken (existing booking lies between chosen dates)")
            clashed = True

    if clashed:
        Pcheck_in_date = inputDate()
        if Pcheck_in_date is None:
            print("Booking cancelled")
            return
        Pcheck_out_date = inputDate()
        if Pcheck_out_date is None:
            print("Booking cancelled")
            return
        saveBooking(property, Pguest, Pcheck_in_date, Pcheck_out_date, Pfee)
    else:
        cursor.execute(
            "INSERT INTO bookings (property_id, guest, check_in, check_out, fee) VALUES (?, ?, ?, ?, ?)",
            (property.id, Pguest, Pcheck_in_date.isoformat(), Pcheck_out_date.isoformat(), Pfee)
        )
        conn.commit()


def createBooking(property):
    rate = inputRate()
    if rate is None:
        print("Booking cancelled")
        return

    guest = input("Enter your guest's name (0 to cancel): ")
    if guest == "0":
        print("Booking cancelled")
        return

    check_in_date = inputDate()
    if check_in_date is None:
        print("Booking cancelled")
        return
    check_out_date = inputDate()
    if check_out_date is None:
        print("Booking cancelled")
        return
    while check_in_date > check_out_date or check_in_date < dt.date.today():
        if check_in_date < dt.date.today():
            print("invalid date, check in cannot be before today")
        else:
            print("invalid date, check out must be after check in")
        check_in_date = inputDate()
        if check_in_date is None:
            print("Booking cancelled")
            return
        check_out_date = inputDate()
        if check_out_date is None:
            print("Booking cancelled")
            return

    total_fee = (check_out_date - check_in_date).days * rate
    saveBooking(property, guest, check_in_date, check_out_date, total_fee)
    createInvoice(property, guest, check_in_date, check_out_date, total_fee)

def inputDate():
    invalid = True
    while invalid:
        raw_day = input("Enter day (0 to cancel): ")
        if raw_day == "0":
            return None
        day = int(raw_day)
        month = int(input("Enter month"))
        year = int(input("Enter year"))
        try:
            date = dt.date(year, month, day)
            invalid = False
        except ValueError:
            print("Invalid date (Value error)")
    return date


def inputRate():
    invalid = True
    while invalid:
        raw = input("Enter rate (0 to cancel): ")
        if raw == "0":
            return None
        try:
            rate = int(raw)
            invalid = False
        except ValueError:
            print("Invalid rate (Value error)")
    return rate


def sortBookings(property, sortingby, reverse=False):
    columns = {0: "id", 1: "check_in", 2: "check_out"}
    column = columns[sortingby]
    order = "DESC" if reverse else "ASC"
    cursor.execute(
        f"SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ? ORDER BY {column} {order}",
        (property.id,)
    )
    return cursor.fetchall()


def showBookings(property, ask_sort=True):
    if ask_sort:
        invalid = True
        while invalid:
            raw = input("enter 1 to sort by check in date, 2 for check out date, 0 for no sorting: ")
            try:
                sortby = int(raw)
                if sortby in (0, 1, 2):
                    invalid = False
                else:
                    print("Please enter 0, 1, or 2")
            except ValueError:
                print("Invalid (Value error)")

        reverse = False
        if sortby != 0:
            direction = input("Enter 1 for earliest first, 2 for latest first: ")
            reverse = (direction == "2")

        display_list = sortBookings(property, sortby, reverse)
    else:
        cursor.execute(
            "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ? ORDER BY id",
            (property.id,)
        )
        display_list = cursor.fetchall()

    count = 1
    for booking in display_list:
        checkIn = dt.date.fromisoformat(booking[2]).strftime("%d/%m/%Y")
        checkOut = dt.date.fromisoformat(booking[3]).strftime("%d/%m/%Y")
        print(str(count) + ")" + booking[1] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[4]))
        count += 1


def deleteBooking(property):
    cursor.execute(
        "SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ? ORDER BY id",
        (property.id,)
    )
    rows = cursor.fetchall()
    count = 1
    for booking in rows:
        checkIn = dt.date.fromisoformat(booking[2]).strftime("%d/%m/%Y")
        checkOut = dt.date.fromisoformat(booking[3]).strftime("%d/%m/%Y")
        print(str(count) + ")" + booking[1] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[4]))
        count += 1

    invalid = True
    while invalid:
        deleted = input("Enter your choice (0 to cancel): ")
        try:
            deleted = int(deleted)
            if deleted == 0:
                invalid = False
            elif 1 <= deleted <= len(rows):
                chosen_booking = rows[deleted - 1]
                booking_check_out = dt.date.fromisoformat(chosen_booking[3])
                if booking_check_out < dt.date.today():
                    print("Cannot delete a past booking")
                else:
                    booking_id = chosen_booking[0]
                    cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
                    conn.commit()
                    invalid = False
            else:
                print("No booking with that number")
        except ValueError:
            print("Invalid (Value error)")


def searchByName(property):
    search = input("Enter name to search for: ")
    cursor.execute("SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ?", (property.id,))
    rows = cursor.fetchall()
    count = 1
    for booking in rows:
        if search.lower() in booking[1].lower():
            checkIn = dt.date.fromisoformat(booking[2]).strftime("%d/%m/%Y")
            checkOut = dt.date.fromisoformat(booking[3]).strftime("%d/%m/%Y")
            print(str(count) + ")" + booking[1] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[4]))
            count += 1
    if count == 1:
        print("No bookings found for that name")


def searchByDate(property):
    print("Enter the date to search for:")
    search_date = inputDate()
    if search_date is None:
        print("Search cancelled")
        return
    cursor.execute("SELECT id, guest, check_in, check_out, fee FROM bookings WHERE property_id = ?", (property.id,))
    rows = cursor.fetchall()
    count = 1
    for booking in rows:
        booking_check_in = dt.date.fromisoformat(booking[2])
        booking_check_out = dt.date.fromisoformat(booking[3])
        if booking_check_in <= search_date <= booking_check_out:
            checkIn = booking_check_in.strftime("%d/%m/%Y")
            checkOut = booking_check_out.strftime("%d/%m/%Y")
            print(str(count) + ")" + booking[1] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[4]))
            count += 1
    if count == 1:
        print("No bookings found for that date")


def createInvoice(property, Pguest, Pcheck_in_date, Pcheck_out_date, Pfee):
    Pcheck_in_date = Pcheck_in_date.strftime("%d/%m/%Y")
    Pcheck_out_date = Pcheck_out_date.strftime("%d/%m/%Y")
    Pfee = str(Pfee)

    c = canvas.Canvas("invoice.pdf", pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 80, "Invoice")

    c.setLineWidth(1)
    c.line(50, height - 90, width - 50, height - 90)

    c.setFont("Helvetica", 12)
    y = height - 130
    line_gap = 25

    c.drawString(50, y, "Property: " + property.name)
    y -= line_gap
    c.drawString(50, y, "Guest: " + Pguest)
    y -= line_gap
    c.drawString(50, y, "Check-in: " + Pcheck_in_date)
    y -= line_gap
    c.drawString(50, y, "Check-out: " + Pcheck_out_date)
    y -= line_gap

    c.line(50, y, width - 50, y)
    y -= line_gap

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Total Fee: £" + Pfee)

    c.save()


def main():
    property = chooseProperty()
    if property is None:
        return

    while True:
        print("--- " + property.name + " ---")
        print("1. Create Booking")
        print("2. See bookings")
        print("3. Remove booking")
        print("4. Search bookings")
        print("5. Switch property")
        choice = input("Choose an option: ")

        if choice == "1":
            createBooking(property)
        elif choice == "2":
            showBookings(property)
        elif choice == "3":
            deleteBooking(property)
        elif choice == "4":
            searchFunction = input("for search by name enter 1, for search by date enter 2: ")
            if searchFunction == "1":
                searchByName(property)
            elif searchFunction == "2":
                searchByDate(property)
            else:
                print("Invalid option")
        elif choice == "5":
            property = chooseProperty()
            if property is None:
                return
        else:
            print("Invalid choice, try again")


main()