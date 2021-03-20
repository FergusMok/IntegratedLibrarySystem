from django.http import HttpResponse,HttpResponseRedirect
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User # The auth User model
from django.contrib import messages
from project.models import Admins, Users, Book, Bookauthor, Borrowreturn, Fine, Payment, Reservecancel
from datetime import datetime, timedelta
from django.db import connection

import re
from pymongo import MongoClient
from django import template
register = template.Library()

#form imports
from .forms import BookSearchForm, DescriptionSearchForm

#model imports
from .models import Users
from .models import Fine
from .models import Borrowreturn
from .models import Reservecancel

# Create your views here.
client = MongoClient("mongodb+srv://Group1:BT2102noice@bt2102g1.hckrp.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")
db = client["Library"]["Books"]

def displayBookCollection():
    collection = []
    for book in db.find():
        collection.append(book)
    return collection


def searchByID(ID):
    collection = []
    for book in db.find({"_id" : ID}):
        collection.append(book)
    return collection


def searchByAuthors(author):
    authorRegex = re.compile(".*" + author + ".*", re.IGNORECASE)
    collection = []
    for book in db.find({"authors" : authorRegex}):
        collection.append(book)
    return collection


def searchByDescription(description):
    authorRegex = re.compile(".*" + description + ".*", re.IGNORECASE)
    collection = []
    for book in db.find({"longDescription" : authorRegex} or {"shortDescription" : authorRegex} ):
        collection.append(book)
    return collection


def searchByISBN(ISBN):
    authorRegex = re.compile(".*" + ISBN + ".*", re.IGNORECASE)
    collection = []
    for book in db.find({"isbn" : authorRegex}):
        collection.append(book)
    return collection

def searchByAuthorsAndDescription(author,description):
    arr1 = searchByAuthors(author)
    arr2 = searchByDescription(description)
    arr3 = [value for value in arr1 if value in arr2]
    return arr3

def index(request):
    bookCollection = displayBookCollection()
    context = {
        'bookCollection':bookCollection,
    }
    return render(request, "project/booklist.html", context)

def bookview(request, id):
    book = searchByID(id)[0]
    context = {
        'book':book,
        'id': book['_id']
    }
    return render(request, 'project/bookview.html', context)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save() # Creation of auth_user
            username = form.cleaned_data.get('username') # Convert to python types
            messages.success(request, f'Account created for {username}!') # flash message

            ## Creation of Users model
            hashedPassword = make_password(form.cleaned_data.get('password1'))
            userId = User.objects.get(username = username).pk
            newUser = Users(userid = userId, userpassword = hashedPassword)
            newUser.save()

            return redirect('home') # Uses the url pattern name

            # auth_user is for the django login service.
            # newUser will grab auth_user's ID and hashed password, and
            # make a new Users instance ( for assignment purposes )

    else:
        form = UserCreationForm()
    return render(request, 'project/register.html', {'form':form})

def adminPage(request):
    if request.user.is_authenticated and request.user.is_superuser:
        print(Fine.objects.all())
        context = {
            "listOfFines": Fine.objects.all(),
            "listOfBorrow": Borrowreturn.objects.all(),
            "listOfReservations": Reservecancel.objects.all(),
        }
        return render(request, 'project/adminPage.html', context)
    else:
        messages.warning(request, f'You do not have sufficient privileges to enter here!') # flash message
        return redirect('home')

def userProfileView(request,id):
    return render(request, 'project/userprofile.html')

"""
def borrowView(request, bookid, userid):
    print(bookid)
    print(userid)
    return render(request, 'project/borrowed.html')
"""

def borrow(request, bookid, userid):
    cursor = connection.cursor()
    cursor.execute("SELECT available FROM Book b WHERE %s = b.bookID", [bookid])
    if not cursor.fetchall()[0][0]:
        messages.warning(request, f'Book has been borrowed.')
        return bookview(request, bookid)
    cursor.execute("SELECT EXISTS(SELECT userID FROM Fine WHERE userID = %s)", [userid])
    if cursor.fetchall()[0][0]:
        messages.warning(request, f'Please pay any outstanding fines before borrowing a book')
        return bookview(request, bookid)
    cursor.execute("SELECT count(userID) FROM BorrowReturn br WHERE %s = br.userID and br.returnDate = null", [userid])
    if cursor.fetchall()[0][0] == 4:
        messages.warning(request, f'Max borrowing limit reached.')
        return bookview(request, bookid)
    else:
        cursor.execute("SELECT EXISTS(SELECT userID, bookID from BorrowReturn br where %s = br.userID and %s = br.bookID)", [userid, bookid])
        if cursor.fetchall()[0][0]:
            cursor.execute("DELETE from BorrowReturn br where %s = br.userID and %s = br.bookID", [userid, bookid])
        cursor.execute("INSERT INTO BorrowReturn VALUES (%s, %s, FALSE, %s, null)", [userid, bookid, (datetime.today() + timedelta(days=28)).strftime('%Y-%m-%d')])
        cursor.execute("UPDATE Book b SET available = FALSE WHERE %s = b.bookID", [bookid])
        return render(request, 'project/borrowed.html')


# def return(request, bookid, userid):
#     cursor = connection.cursor()
#     cursor.execute("UPDATE BorrowReturn br set returnDate = %s where %s = br.bookID and %s = br.userID", [datetime.today(), bookid, userid])
#     cursor.execute("SELECT EXISTS(SELECT bookID FROM ReserveCancel rc where %s = rc.bookID)", [bookid])
#     if cursor.fetchall()[0][0]:
#         cursor.execute("UPDATE Book b SET available = TRUE WHERE %s = b.bookID", [bookid])
#     return render(request, 'project/returned.html') #NEED TO MAKE RETURN BUTTON AND RETURNED HTML PAGE


def reserve(request, bookid, userid):
    cursor = connection.cursor()
    cursor.execute("SELECT EXISTS(SELECT userID FROM fine f where %s = f.userID)", [userid])
    if cursor.fetchall()[0][0]:
        messages.warning(request, f'Please pay any outstanding fines before reserving a book.')
        return bookview(request, bookid)
    cursor.execute("SELECT EXISTS(SELECT bookID FROM ReserveCancel rc where %s = rc.bookID)", [bookid])
    if cursor.fetchall()[0][0]:
        messages.warning(request, f'Unable to reserve. Book has been reserved by another user.')
        return bookview(request, bookid)
    cursor.execute("INSERT INTO ReserveCancel VALUES (%s, %s, (Select dueDate from book b where %s = b.bookID))", [userid, bookid, bookid])
    cursor.execute("UPDATE Book b SET availability = FALSE WHERE %s = b.bookId", [bookid])
    return render(request, 'project/reserved.html') #NEED TO MAKE RESERVE BUTTON AND RESERVED HTML PAGE


def cancelRes(request, bookid, userid):
    cursor = connection.cursor()
    cursor.execute("Delete from ReserveCancel rc where %s = rc.userID and %s = rc.bookID", [userid, bookid])
    cursor.execute("SELECT EXISTS(SELECT bookID, returnDate from BorrowReturn br where %s = br.bookID and returnDate is not null)", [bookid])
    if cursor.fetchall()[0][0]:
        cursor.execute("UPDATE Book b SET available = TRUE WHERE %s = b.bookID", [bookid])
    return render(request, 'project/canceled.html') #NEED TO MAKE CANCELRES BUTTON AND CANCELED HTML PAGE


def searchView(request):
    if request.method == 'POST':
        form = BookSearchForm(request.POST)
        if form.is_valid():
            authorSearch = form.cleaned_data["query"]
            bookCollection = searchByAuthors(authorSearch)
            return render(request, 'project/searchresults.html', {'bookCollection':bookCollection})
    else:
        form = BookSearchForm()
    return render(request, 'project/searchbook.html', {'form':form})

def searchView2(request):
    if request.method == 'POST':
        form = DescriptionSearchForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            bookCollection = searchByDescription(query)
            return render(request, 'project/searchresults.html', {'bookCollection':bookCollection})
    else:
        form2 = DescriptionSearchForm()
    return render(request, 'project/searchbook2.html', {'form2':form2})



### Should work, but I can't test until reserve is done
def fineUsers(request):
    if request.user.is_superuser:

        # 1.From BorrowReturn, query all the users that have null returnDate, AND have dueDate that is less than currentDate.
        userList =  list(Borrowreturn.objects.filter(returndate = None, duedate__lte = datetime.today()))

        # 2.Find these users, and search if they are in the Fine table.
        # if not, create a new entry, and add the fine.
        # if yes, then just add the fine to the current amount
        for user in userList:
            fineUser = Fine.objects.get(userid = user.userid)
            if fineUser:
                fineUser.fine += 1
                fineUser.save()
            else:
                newUser = Fine.objects.create(userid = user.userid, fine = 1);
                newUser.save()

        # 3. Using these users, go to the ReserveCancel table, and delete them from the table.
        for user in userList:
            reserveUser = Reservecancel.objects.get(userid = user.userid)
            if reserveUser:
                reserveUser.delete()

        return redirect('home')

    else:
        messages.warning(request, f'You do not have sufficient privileges to enter here!') # flash message
        return redirect('home')
