import datetime as dt
bookings = []
def saveBooking(Pguest, Pcheck_in_date, Pcheck_out_date,Pfee):
    #check if there are clashes
    clashed = False
    for booking in bookings:
        if Pcheck_in_date <= booking[1] <= Pcheck_out_date: #if checkin is between an existing booking
            print ("dates taken")
            clashed = True
        elif Pcheck_in_date <= booking[2] <= Pcheck_out_date: #if checkout is in between an existing booking
            print ("dates taken")
            clashed = True
        elif Pcheck_in_date > Pcheck_out_date: #if the check in is after the check out it is invalid
            print ("invalid date")
            clashed = True
        elif  Pcheck_in_date >= booking[1] and booking [2] <= Pcheck_out_date:
            # if check in is before the said existing booking
            # and the check out is after the existing booking
            # the existing booking lies between the new booking so the dates are taken
            print ("dates taken")
            clashed = True
    if clashed:
            Pcheck_in_date = inputDate()
            Pcheck_out_date = inputDate()
    else:
        newBooking = [Pguest, Pcheck_in_date, Pcheck_out_date,Pfee]
        bookings.append(newBooking)
def createBooking(pRate):
    guest = input("Enter your guest's name: ")
    check_in_date = inputDate()
    check_out_date = inputDate()
    total_fee = (check_out_date - check_in_date).days*pRate
    saveBooking(guest,check_in_date,check_out_date,total_fee)
def inputDate():
    day = int(input("Enter day"))
    month = int(input ("Enter month"))
    year = int(input ("Enter year"))
    date = dt.date(year, month, day)
    return date
def main(): # mainloop
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
            print (bookings)
        elif choice == "3":
            break  # exits the while loop
        else:
            print("Invalid choice, try again")

main()