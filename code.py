import datetime as dt
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

conn = sqlite3.connect("bookings.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest TEXT,
        check_in TEXT,
        check_out TEXT,
        fee REAL
    )
""")
conn.commit()


def saveBooking(Pguest, Pcheck_in_date, Pcheck_out_date, Pfee):
    clashed = False
    cursor.execute("SELECT id, guest, check_in, check_out, fee FROM bookings")
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
        Pcheck_out_date = inputDate()
        saveBooking(Pguest, Pcheck_in_date, Pcheck_out_date, Pfee)
    else:
        cursor.execute(
            "INSERT INTO bookings (guest, check_in, check_out, fee) VALUES (?, ?, ?, ?)",
            (Pguest, Pcheck_in_date.isoformat(), Pcheck_out_date.isoformat(), Pfee)
        )
        conn.commit()


def createBooking(pRate):
    guest = input("Enter your guest's name: ")
    check_in_date = inputDate()
    check_out_date = inputDate()
    while check_in_date > check_out_date or check_in_date < dt.date.today():  # CHANGED
        if check_in_date < dt.date.today():
            print("invalid date, check in cannot be before today")
        else:
            print("invalid date, check out must be after check in")
        check_in_date = inputDate()
        check_out_date = inputDate()
    total_fee = (check_out_date - check_in_date).days * pRate
    saveBooking(guest, check_in_date, check_out_date, total_fee)
    createInvoice(guest, check_in_date, check_out_date, total_fee)

def inputDate():
    invalid = True
    while invalid:
        day = int(input("Enter day"))
        month = int(input("Enter month"))
        year = int(input("Enter year"))
        try:
            date = dt.date(year, month, day)
            invalid = False
        except ValueError:
            print("Invalid date (Value error)")
    return date


def sortBookings(sortingby, reverse=False):
    columns = {0: "id", 1: "check_in", 2: "check_out"}
    column = columns[sortingby]
    order = "DESC" if reverse else "ASC"
    cursor.execute(f"SELECT id, guest, check_in, check_out, fee FROM bookings ORDER BY {column} {order}")
    return cursor.fetchall()


def showBookings(ask_sort=True):
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

        display_list = sortBookings(sortby, reverse)
    else:
        cursor.execute("SELECT id, guest, check_in, check_out, fee FROM bookings ORDER BY id")
        display_list = cursor.fetchall()

    count = 1
    for booking in display_list:
        checkIn = dt.date.fromisoformat(booking[2]).strftime("%d/%m/%Y")
        checkOut = dt.date.fromisoformat(booking[3]).strftime("%d/%m/%Y")
        print(str(count) + ")" + booking[1] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[4]))
        count += 1


def deleteBooking():
    cursor.execute("SELECT id, guest, check_in, check_out, fee FROM bookings ORDER BY id")
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

def searchByDate():
    print("Enter the date to search for:")
    search_date = inputDate()
    cursor.execute("SELECT id, guest, check_in, check_out, fee FROM bookings")
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


def createInvoice(Pguest, Pcheck_in_date, Pcheck_out_date, Pfee):
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
    while True:
        print("1. Create Booking")
        print("2. See bookings")
        print("3. Remove booking")
        print("4. Search bookings")
        choice = input("Choose an option: ")

        if choice == "1":
            rate = int(input("Enter rate: "))
            createBooking(rate)
        elif choice == "2":
            showBookings()
        elif choice == "3":
            deleteBooking()
        elif choice == "4":
            searchFunction = input("for search by name enter 1, for search by date enter 2: ")
            if searchFunction == "1":
                searchByName()
            elif searchFunction == "2":
                searchByDate()
            else:
                print("Invalid option")
        else:
            print("Invalid choice, try again")


main()