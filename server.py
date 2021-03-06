"""Hiking Trails"""


from jinja2 import StrictUndefined

from flask import Flask, render_template, redirect, request, flash, session, jsonify
from flask_debugtoolbar import DebugToolbarExtension

from model import User, Trail, UserTrail, Hike, connect_to_db, db

import geocoder
import requests
import os
import datetime
import dateutil.parser
import hashlib
import sendgrid
from sendgrid.helpers.mail import *
from sqlalchemy import func
from geopy.geocoders import Nominatim


app = Flask(__name__)


# Required to use Flask sessions and the debug toolbar
app.secret_key = "ABC"

# Normally, if you use an undefined variable in Jinja2, it fails
# silently. This is horrible. Fix this so that, instead, it raises an
# error.
app.jinja_env.undefined = StrictUndefined

hiking_consumer_key = os.environ['HIKING_CONSUMER_KEY']
sendgrid_key = os.environ['SENDGRID_KEY']


@app.route('/')
def index():
    """Homepage."""
    return render_template("homepage.html")


@app.route('/SignIn', methods=["GET"])
def sign_in():
    """Login page."""
    return render_template("login_form.html")


@app.route("/SignIn", methods=["POST"])
def user_sign_in():
    """ Validate User Login """

    email = request.form.get("email")
    password = request.form.get("password")
    query_user = User.query.filter_by(email=email).first()
    #h_password = hashlib.sha1(password).hexdigest()

    if not query_user:
        flash("That email isn't in our system.  It looks like you need to sign up!")
        return redirect("/SignUp")

    if query_user.password != password:
        flash("Incorrect password, please try signing in again")
        return redirect("/SignIn")
    else:
        session['id'] = query_user.user_id
        flash("Login successful!")
        return redirect("/users/" + str(query_user.user_id))


@app.route('/SignUp', methods=["GET"])
def sign_up():
    """Sign Up page"""
    return render_template("signup_form.html")


@app.route("/SignUp", methods=["POST"])
def user_sign_up():
    """ Get User's email and password and adds user to the DB"""

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    zipcode = request.form.get("zip")
    query = db.session.query('User')
    users_emails = query.filter(User.email == email).all()
    #hash_password = hashlib.sha1(password).hexdigest()

    if users_emails:
        flash("User already exists!")
        return redirect('/SignUp')
    else:
        new_user = User(email=email, password=password, zipcode=zipcode, name=name)
        db.session.add(new_user)
        db.session.commit()

        flash("Registered successfully!")

        new_user = User.query.filter_by(email=email).first()
        session['id'] = new_user.user_id
        return redirect('/search')


@app.route("/users/<u_id>")
def user_profile(u_id):
    """Shows details about a specific user."""

    user = User.query.options(db.joinedload('usertrails', 'trail')).get(u_id)

    #Collect data for chartJS that how many hikes done in each month, so check hike list for the user and for each hike month.
    num_jan = 0
    num_feb = 0
    num_march = 0
    num_april = 0
    num_may = 0
    num_june = 0
    len_jan = 0
    len_feb = 0
    len_march = 0
    len_april = 0
    len_may = 0
    len_june = 0
    hike_num_list = []
    hike_len_list = []

    if user.usertrails:
        for usertrail in user.usertrails:
            for hike in usertrail.hikes:
                date = hike.date

                if date.month == 1:
                    len_jan = float("{0:.2f}".format(len_jan + hike.usertrail.trail.length))
                    num_jan = num_jan + 1
                elif date.month == 2:
                    len_feb = float("{0:.2f}".format(len_feb + hike.usertrail.trail.length))
                    #len_feb = float(len_feb + hike.usertrail.trail.length)
                    num_feb = num_feb + 1
                elif date.month == 3:
                    len_march = float("{0:.2f}".format(len_march + hike.usertrail.trail.length))
                    num_march = num_march + 1
                elif date.month == 4:
                    len_april = float("{0:.2f}".format(len_april + hike.usertrail.trail.length))
                    num_april = num_april + 1
                elif date.month == 5:
                    len_may = float("{0:.2f}".format(len_may + hike.usertrail.trail.length))
                    num_may = num_may + 1
                elif date.month == 6:
                    len_june = float("{0:.2f}".format(len_june + hike.usertrail.trail.length))
                    num_june = num_june + 1

        hike_num_list = [num_jan, num_feb, num_march, num_april, num_may, num_june]
        hike_len_list = [len_jan, len_feb, len_march, len_april, len_may, len_june]

    visited_trail_names = [usertrail.trail.name for usertrail in user.usertrails]
    unique_visited = list(set(visited_trail_names))

    list_lat = []
    list_lng = []

    for trail in unique_visited:
        place = geocoder.google(str(trail))
        place_lat = str(place.lat)
        place_lng = str(place.lng)  
        # geolocator = Nominatim()
        # location = geolocator.geocode(trail)
        # place_lat = location.latitude
        # place_lng = location.longitude  
         
        list_lat.append(float(place_lat))
        list_lng.append(float(place_lng))

    average_lat = sum(list_lat) / len(list_lat)
    average_lng = sum(list_lng) / len(list_lng)
    number = len(unique_visited)
    print unique_visited
    print list_lat
    print list_lng

    #Collect data for CharJs that how many miles hiked in each month - so check hike list for the user for each month and calculate lenght

    return render_template("user_detail.html", user=user, hike_num_list=hike_num_list, hike_len_list=hike_len_list, list_lat=list_lat, list_lng=list_lng, number=number, average_lng=average_lng, average_lat=average_lat, unique_visited=unique_visited)


@app.route("/search", methods=["GET"])
def search_trails():
    """Search form"""
    if session['id']:
        user = User.query.options(db.joinedload('usertrails', 'trail')).get(session['id'])
        trails = db.session.query(UserTrail.trail_id).group_by(UserTrail.trail_id).having(func.count(UserTrail.trail_id) > 2).filter(UserTrail.user_id == session['id']).all()

        frequently_visited_trails = []
        for trail in trails:
            trail_record = Trail.query.filter_by(trail_id=trail).first()
            frequently_visited_trails.append(trail_record)

    return render_template("search_form.html", user=user, trail_list=frequently_visited_trails)


@app.route("/search", methods=["POST"])
def user_search_trails():
    """Display search results"""

    zipcode = request.form.get("zipcode")
    location = request.form.get("location")
    if zipcode:
        g = geocoder.google(str(zipcode))
        url_lat = str(g.lat)
        url_lng = str(g.lng)
    else:
        g = geocoder.google(str(location))
        url_lat = str(g.lat)
        url_lng = str(g.lng)

    url_maxResults = request.form.get("trail_num")
    if not url_maxResults:
        url_maxResults = str(10)

    #send request with above lat and long
    r = requests.get("https://www.hikingproject.com/data/get-trails?lat="+url_lat+"&lon="+url_lng+"&maxDistance=10&maxResults="+url_maxResults+"&key="+hiking_consumer_key)
    trail = r.json()
    print trail
    num_results = trail['trails']
    number = len(num_results)
    #print num_results

    user_id = session['id']
    user = User.query.options(db.joinedload('usertrails', 'trail')).get(user_id)

    visited_names = [usertrail.trail.name for usertrail in user.usertrails]
    unique_visited = list(set(visited_names))

    return render_template("search_results.html", dict=trail, num_results=num_results, number=number, lat=url_lat, lng=url_lng, user=user, visited_names=unique_visited)


@app.route("/get-trails-info", methods=["POST"])
def get_trail_info_add_to_db():
    """Get Trail info from front end when user selects and stores in DB"""

    trail_id = request.form.get("trail_id")
    date = request.form.get("date")
    user_id = session['id']
    name = request.form.get("name")
    url = request.form.get("url")
    length = request.form.get("length")
    trail_type = request.form.get("type")
    rating = request.form.get("stars")

    #Add this record in Trail, UserTrails and Hike Table

    #Need to check if same trail with same date exists in Hike Table already then flash the message
    #to the user - You have already added this Hike!

    #Need to check if this record already exists in Trails then don't add it in Trails
    query = db.session.query(Trail)
    users_trails = query.filter(Trail.trail_id == trail_id).all()

    if not users_trails:
        trail = Trail(trail_id=trail_id, name=name, url=url, length=length, trail_type=trail_type)
        db.session.add(trail)
        db.session.commit()

    usertrails = UserTrail(trail_id=trail_id, user_id=user_id, rating=rating)
    db.session.add(usertrails)
    db.session.commit()

    usertrail_id = usertrails.usertrail_id

    parsed_date = dateutil.parser.parse(date).date()
    print parsed_date
    hike = Hike(usertrail_id=usertrail_id, date=parsed_date)
    db.session.add(hike)
    db.session.commit()

    flash("you just added " + name + " to your hike list!")

    return jsonify({"trail_id": trail_id})


@app.route("/add-trails-comment", methods=["POST"])
def add_trail_comment_add_to_db():
    """Get Hike Comment from front end and store it in Hike Table"""

    trail_id = request.form.get("trail_id")
    comments = request.form.get("comments")
    hike_id = request.form.get("hike_id")

    #Update comment in Hikes table for the specific hike object
    hike = db.session.query(Hike).filter_by(hike_id=hike_id).first()

    hike.comments = comments
    db.session.commit()

    return jsonify({"trail_id": trail_id})


@app.route("/add-rating", methods=["POST"])
def add_trail_rating_add_to_db():
    """Get Hike Comment from front end and store it in Hike Table"""

    #trail_id = request.form.get("trail_id")
    u_rating = request.form.get("u_rating")
    hike_id = request.form.get("hike_id")

    #Update comment in Hikes table for the specific hike object
    hike = db.session.query(Hike).filter_by(hike_id=hike_id).first()

    hike.u_rating = u_rating
    db.session.commit()

    return jsonify({"hike_id": hike_id})


@app.route("/send-email", methods=["POST"])
def send_email():
    """ Send Email to Receipent """

    hike_id = request.form.get("hike_id")
    trail_name = request.form.get("trail_name")
    T_email = request.form.get("re_email")
    F_email = request.form.get("se_email")
    trail_url = request.form.get("trail_url")
    trail_length = request.form.get("trail_length")
    user_name = request.form.get("user_name")

    hike = db.session.query(Hike).filter_by(hike_id=hike_id).first()

    user_comment = hike.comments
    user_rating = str(hike.u_rating)

    custom_message = '<br>' + '<br>' + user_name + " is recommending this trail to you" + '<br>' + "Trail Name: " + trail_name + '<br>' + "Trail URL: " + trail_url + '<br>' + "Trail Length: " + trail_length + " miles" + '<br>' + user_name + "\'s comment: " + user_comment + '<br>'+ user_name + "\'s rating: " + user_rating
    message = request.form.get("message") + custom_message

    sg = sendgrid.SendGridAPIClient(apikey=sendgrid_key)
    from_email = Email(F_email)
    to_email = Email(T_email)
    message = request.form.get("message") + custom_message

    sg = sendgrid.SendGridAPIClient(apikey=sendgrid_key)
    from_email = Email(F_email)
    to_email = Email(T_email)
    subject = "Trail Recommendtion from GoHike"
    content = Content("text/html", message)

    mail = Mail(from_email, subject, to_email, content)
    try:
        response = sg.client.mail.send.post(request_body=mail.get())
        print(response.status_code)
    except Exception as e:
        print (e.body)

    return jsonify({"trail_name": trail_name})


@app.route("/logout")
def user_logout():
    """ Logout User and Redirect to Homepage """

    if session:
        session.clear()

    return redirect('/')


if __name__ == "__main__":
    # We have to set debug=True here, since it has to be True at the
    # point that we invoke the DebugToolbarExtension
    app.debug = True
    # make sure templates, etc. are not cached in debug mode
    app.jinja_env.auto_reload = app.debug

    connect_to_db(app, "hiking")

    # Use the DebugToolbar
    # DebugToolbarExtension(app)
    # app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

    app.run(port=5000, host='0.0.0.0')
