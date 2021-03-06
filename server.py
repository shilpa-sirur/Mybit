
from data_model import User, Event, Registration, Student, Parent_Child
from flask import Flask,render_template, redirect, request, flash, session,jsonify
from flask_debugtoolbar import DebugToolbarExtension

from data_model import *  # please fix this importing * (everything) can cause a conflict
from sqlalchemy.sql import label
from sqlalchemy import *  # please fix this importing * (everything) can cause a conflict
from datetime import date, datetime
from send_app_email import send_notification
from email_template import EmailTemplate
from sqlalchemy.ext.serializer import loads, dumps
import json
from sqlalchemy.ext import serializer
from sm_response_api import get_sm_survey_respondent_ids,get_sm_survey_response
from create_event import get_credentials,create_event
from sqlalchemy import desc
from send_sms import send_twillio_sms

app = Flask(__name__)

# The secret key is required to use Flask sessions and the debug toolbar
app.secret_key = "ABC"


@app.route('/', methods=['GET'])
def login_form():
    """Show login form."""

    return render_template("login.html")


@app.route('/sign_in', methods=['POST'])
def login_process():
	"""Process login."""

	# Get login.html form variables
	email = request.form.get("email")
	# print email
	passwd = request.form.get("password")
	# Query the database to find if the user sign in email exists
	user_count = User.query.filter_by(email_address=email).count()
	# Sign in and if that email address doesn't exist in the database

	if user_count==0:
		flash("No such user")
		return render_template("signup.html")
	else:
		# If the email address existed in the database,query to filter the User model class for all the records for that email address and assign to an object called user
		user = User.query.filter_by(email_address=email).one()
		# print user
		# print user.user_id
		# Verify if the password stored in the database matches the one provided in from the login form, if yes then add the email_address and password to the session
		if user.password == passwd:
			session["user_id"] = user.user_id
			session["email"] = email
			session["first_name"] = user.first_name
			session["last_name"] = user.last_name

			#flash("Logged in")
			# print "Logged in"
			# print session["user_id"]
			# print user.user_type
			# Checking if the user is Admin or a User
			if user.user_type == 'Admin':
				sign_up = db.session.query(Event.event_id,Event.event_name,Event.event_description,Event.event_date,Event.event_status,Event.no_of_spots, Event.no_of_reg_spots,Event.no_of_waitlist_spots, label('filluppercent',((Event.no_of_reg_spots + Event.no_of_waitlist_spots)*100 )/Event.no_of_spots)).order_by(asc(Event.event_date)).filter(Event.event_date >= date.today() ).all()
				user_registration = Registration.query.filter_by(showup="Yes").subquery()
				past_sign_up = db.session.query(Event.event_id,Event.event_name,Event.event_description,Event.event_date,Event.event_status,Event.no_of_spots, Event.no_of_reg_spots,Event.no_of_waitlist_spots, func.sum(user_registration.c.slot_id).label("Attended")).order_by(asc(Event.event_date)).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date < date.today() ).all()
		   		return render_template("admin.html",user=user,sign_up=sign_up,past_sign_up=past_sign_up)
		   	else:
		   		# Get the user_id(parent_id with the user object)
				parent = user.user_id
				
				# why are we querying the mandated and how
				mandated = db.session.query(Parent_Child.parent_id,label('children',func.count(Parent_Child.student_id))).group_by(Parent_Child.parent_id).filter_by(parent_id=parent).first()
				print mandated
				
				#querying for children 
				children = db.session.query(Student.student_id,Student.first_name,Student.last_name,Student.grade,Student.year_joined,Student.status ).join(Parent_Child).filter(Parent_Child.parent_id==parent).all()
				#if there is None for the mandated from the database
				if mandated is not None:
					total_hours = mandated.children*10
				else:
					total_hours = 0
				#print total_hours

				#querying for completed hours
				completed = db.session.query(Registration.parent_id,label('slots',func.count(Registration.slot_id))).group_by(Registration.parent_id).filter_by(parent_id=parent , showup='Yes').first()
				
				# print completed
				
				#if there is None from the database for completed hours
				if completed is not None:
					completed_hours = completed.slots*2
				else:
					completed_hours = 0
				# print completed_hours


				# Calculating the percentage of completion of volunteering
				if completed_hours != 0 and total_hours != 0:
					# print ("I am in if for percentcomplete")
					percentcomplete = float(completed_hours)/float(total_hours) * 100
				elif completed_hours == 0 and total_hours != 0:
					# print ("I am in elseif for percentcomplete")
					percentcomplete = 0
				else:
					percentcomplete = 0
				# print "Below "
				# print int(percentcomplete)

				# Calculating the remaining hours of volunteering
				remaining_hours = total_hours-completed_hours
				# what is this doing?
				user_registration = Registration.query.filter_by(parent_id=parent).subquery()
				print user_registration
				
				sign_up = db.session.query(Event.event_id,Event.event_name,Event.event_description,Event.event_date,Event.event_status,label('no_of_remaining_spots',Event.no_of_spots - Event.no_of_reg_spots),user_registration.c.parent_id,user_registration.c.status).order_by(asc(Event.event_date)).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date >= date.today() ).all()
				print sign_up
				past_sign_up = db.session.query(Event.event_id,Event.event_name,Event.event_description,Event.event_date,Event.event_status,Event.no_of_spots, Event.no_of_reg_spots,Event.no_of_waitlist_spots,Registration.showup).join(Registration).order_by(asc(Event.event_date)).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date < date.today()).all()

				
				# print "before render_template"
				# print children
				# print total_hours
				# print completed_hours
				# print remaining_hours
				# print percentcomplete
				# print past_sign_up
				# print sign_up
				# print user

			   	return render_template("welcome.html",first_name=session["first_name"],last_name=session["last_name"],user=user,children=children,mandated=total_hours,completed=completed_hours,remaining_hours=remaining_hours, percentcomplete = int(percentcomplete), sign_up=sign_up, past_sign_up=past_sign_up)
		
		#if the password stored in the database doesn't matches the one provided in from the login form for that particular email address. Flash wrong message. 	   	
		else:
			flash("The password is incorrect. Please try again")
			return render_template("login.html")

@app.route('/event_signup_confirmed', methods=['POST'])
def signup_process():
	"""Add Event signup order to our database."""
	# Decoding the JSON object getting from the 
	parent_id = request.form['userid']
	event_id = request.form['eventid']
	op = request.form['opcode']

	# print "Activity id i populated below"
	# print event_id
	# print op

	if op == "register":

		#updating - increment the no_of_reg_spots by 1 in the database column no_of_reg_spots
		register_event = Registration(parent_id=parent_id, event_id=event_id,slot_id=1,registration_date = datetime.now(),status = 'Registered',showup="")
		db.session.add(register_event)
		update_no_of_reg_spots = Event.query.get(event_id)
		update_no_of_reg_spots.no_of_reg_spots += 1
		db.session.commit()
	    
		# Integrating the Gmail API and making a call to the mailer
		# print session["email"]
		# print ('before sending Register email')
		
		eventmessage = {}
		eventmessage['eventname'] = update_no_of_reg_spots.event_name
		eventmessage['eventdate'] = update_no_of_reg_spots.event_date.strftime("%B %d, %Y")
		eventmessage['eventdesc'] = update_no_of_reg_spots.event_description
 		
 		# print eventmessage

 		# print ('before sending email template email')

		templateobj = EmailTemplate(template_name='registration.txt', values=eventmessage)
		message = templateobj.render()

		print ('before sending before actual email')

		print registerSub
		print message

		send_notification(session["email"],registerSub,message)

		print ('before sending Register email')

		# user_registration = Registration.query.filter_by(parent_id=parent).subquery()
		# signupObj = {}
		# sign_up = db.session.query(Event.event_id,Event.event_name,Event.event_description,Event.event_date,Event.event_status,label('no_of_remaining_spots',Event.no_of_spots - Event.no_of_reg_spots),user_registration.c.parent_id,user_registration.c.status).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date >= date.today(), Event.event_id == event_id ).all()
		# for item in sign_up:
		# 	# signupObj["event_id"] = item.event_id
		# 	# signupObj["event_name"] = item.event_name
		# 	# signupObj["event_description"] = item.event_description
		# 	# signupObj["event_date"] = item.event_date
		# 	# signupObj["no_of_remaining_spots"] = item.no_of_remaining_spots
		# 	signupObj["status"] = item.status


		#print signupObj
		#print jsonify(register_event)
		
		print "jsonyfy works"
		user_registration = Registration.query.filter_by(parent_id=session["user_id"]).subquery()
		sign_up = db.session.query(Event.event_id,Event.no_of_waitlist_spots,Event.event_name,Event.event_description,Event.event_status,label('no_of_remaining_spots',Event.no_of_spots - Event.no_of_reg_spots),user_registration.c.parent_id,user_registration.c.status).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date >= date.today(), Event.event_id == event_id ).all()
		#print jsonify(dumps(sign_up))

		for i in sign_up:
			x = i
			print x.no_of_waitlist_spots

		return jsonify(json_list = x )


		#return jsonify(register_event)

	# print "Shilpa updating count"
	# print update_no_of_reg_spots.no_of_reg_spots
	elif op == "waitlist":

		#updating - increment the no_of_waitlisted_spots by 1 in the database column no_of_reg_spots
		register_event = Registration(parent_id=parent_id, event_id=event_id,slot_id=1,registration_date = datetime.now(),status = 'Waitlisted',showup="")
		db.session.add(register_event)
		update_no_of_waitlist_spots = Event.query.get(event_id)
		update_no_of_waitlist_spots.no_of_waitlist_spots += 1
		db.session.commit()
		# print "I am in waitlist"
	    
		
		# print session["email"]
		# print ('before sending Register email')
		
		eventmessage = {}
		eventmessage['eventname'] = update_no_of_waitlist_spots.event_name
		eventmessage['eventdate'] = update_no_of_waitlist_spots.event_date.strftime("%B %d, %Y")
		eventmessage['eventdesc'] = update_no_of_waitlist_spots.event_description
 		
 		# print eventmessage

 		# print ('before sending email template email')

		templateobj = EmailTemplate(template_name='waitlist.txt', values=eventmessage)
		message = templateobj.render()

		# print ('before sending before actual email')

		# print registerSub
		# print message

		# Integrating the Gmail API and making a call to the mailer
		send_notification(session["email"],registerSub,message)

		print ('before sending Register email')

		# user_registration = Registration.query.filter_by(parent_id=parent).subquery()
		# signupObj = {}
		# sign_up = db.session.query(Event.event_id,Event.event_name,Event.event_description,Event.event_date,Event.event_status,label('no_of_remaining_spots',Event.no_of_spots - Event.no_of_reg_spots),user_registration.c.parent_id,user_registration.c.status).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date >= date.today(), Event.event_id == event_id ).all()
		# for item in sign_up:
		# 	# signupObj["event_id"] = item.event_id
		# 	# signupObj["event_name"] = item.event_name
		# 	# signupObj["event_description"] = item.event_description
		# 	# signupObj["event_date"] = item.event_date
		# 	# signupObj["no_of_remaining_spots"] = item.no_of_remaining_spots
		# 	signupObj["status"] = item.status


		#print signupObj
		#print jsonify(register_event)
		
		# print "jsonyfy works"
		user_registration = Registration.query.filter_by(parent_id=session["user_id"]).subquery()
		sign_up = db.session.query(Event.event_id,Event.no_of_waitlist_spots,Event.event_name,Event.event_description,Event.event_status,label('no_of_remaining_spots',Event.no_of_spots - Event.no_of_reg_spots),user_registration.c.parent_id,user_registration.c.status).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date >= date.today(), Event.event_id == event_id ).all()
		#print jsonify(dumps(sign_up))

		for i in sign_up:
			x = i
			# print x.no_of_waitlist_spots

		return jsonify(json_list = x )

		#return jsonify(register_event)

		# print "Shilpa updating count"
		# print update_no_of_reg_spots.no_of_reg_spots
	else:
		#Checking if the op = "cancel"
		print "Inside else block"
		print event_id
		print parent_id

		update_reg_status = Registration.query.filter_by(event_id=event_id,parent_id=parent_id).one()
		update_reg_status.status = 'Cancelled'
		# Finding the minimum reistration for an event id with waitlisted status
		waitlisted_regid = db.session.query(func.min(Registration.registration_id).label('min_reg_id')).filter( event_id==event_id,Registration.status == 'Waitlisted').one()
		# Bringing the whole record(object)
		# When the cancel is happening
		# update the database column no_of_spots decrement by 1
		# If a user is not in the waitlist
		if  waitlisted_regid:
			print "I am in null"
			update_no_of_spots = Event.query.get(event_id)
			update_no_of_spots.no_of_reg_spots -= 1
		else :
			#moving from waitlisted to registration action
			#decrement waitlist spots by 1
			#increment no of registered spots by 1
			who_is_waitlisted = Registration.query.filter(Registration.registration_id== waitlisted_regid.min_reg_id ).one()
			who_is_waitlisted.status = 'Registered'
			update_no_of_waitspots = Event.query.get(event_id)
			update_no_of_waitspots.no_of_waitlist_spots -=1
			who_is_waitlisted_user = User.query.filter_by(user_id = who_is_waitlisted.parent_id).one()
			sms_message = "Dear "+who_is_waitlisted_user.first_name+" "+who_is_waitlisted_user.last_name+" Your reservaton for event "+update_no_of_waitspots.event_name+" on "+update_no_of_waitspots.event_date.strftime("%B %d, %Y")+" has bee confirmed. Please make changes by signing to MySignUp application. Enjoy and Engage with kids - MySignUp Team"
			send_twillio_sms(sms_message,who_is_waitlisted_user.phone_number)
		db.session.commit()
	    
		# Integrating the Gmail API and making a call to the mailer
		# print session["email"]
		# print ('before sending cancelling ****** email')

		eventmessage = {}
		eventmessage['eventname'] = update_no_of_spots.event_name
		eventmessage['eventdate'] = update_no_of_spots.event_date.strftime("%B %d, %Y")
		eventmessage['eventdesc'] = update_no_of_spots.event_description
 		
 		# print eventmessage

 		# print ('before sending email template email')

		templateobj = EmailTemplate(template_name='cancellation.txt', values=eventmessage)
		message = templateobj.render()

		# print ('before sending before actual email')

		# Integrating the Gmail API and making a call to the mailer
		send_notification(session["email"],registerCancel,message)


		#send_notification(session["email"],'You are all set for baking','Test the function')
		print "jsonyfy works"
		user_registration = Registration.query.filter_by(parent_id=session["user_id"]).subquery()
		sign_up = db.session.query(Event.event_id,Event.no_of_waitlist_spots,Event.event_name,Event.event_description,Event.event_status,label('no_of_remaining_spots',Event.no_of_spots - Event.no_of_reg_spots),user_registration.c.parent_id,user_registration.c.status).outerjoin(user_registration,Event.event_id==user_registration.c.event_id).filter(Event.event_date >= date.today(), Event.event_id == event_id ).all()
		#print jsonify(dumps(sign_up))
		# 
		for i in sign_up:
			x = i
			# print x
			# print x.no_of_waitlist_spots
		# x is the tuple that needs to be jsonified(as key-value pairs) to give to javascript
		return jsonify(json_list = x )


@app.route('/admin_edit/save_confirmed', methods=['POST'])
def admin_page():
	"""Update Admin changes to our database."""

	# print "I am in the method"
	#import pdb; pdb.set_trace()

	event_id = request.form.get("eventid")
	event_name = request.form.get("eventname")
	event_date = request.form.get("eventdate")
	event_description = request.form.get("eventdesc")
	event_status = request.form.get("eventstatus")
	event_spots = request.form.get("noofspots")
	print "*********************************************************"
	print event_id
	print event_name
	print datetime
	print event_description
	print event_status
	print event_spots
	print "*********************************************************"
	print event_id , event_name,event_date,event_description,event_status,event_spots
	event_count = Event.query.filter_by(event_id=event_id).count()
	print event_count
	if event_count == 0 :
		new_event = Event(event_name=event_name,event_date=datetime.strptime(event_date , '%Y-%m-%d'),event_length=1,event_description=event_description,event_status=event_status,no_of_spots=event_spots,no_of_reg_spots=0,no_of_waitlist_spots=0,recurring='Yes' ,created_id=500 )
		print "I am inside insert *****************************"
		print event_name
		print event_date
		print event_description
		print event_status
		print event_spots
		print "########*********************************************************"

		eventmessage = {}
		eventmessage['eventname'] = event_name
		eventmessage['eventdate'] = event_date
		eventmessage['eventdesc'] = event_description
		print "*********************************************************########"
		
		db.session.add(new_event)

		db.session.commit()
		
		print eventmessage

		templateobj = EmailTemplate(template_name='eventadd.txt', values=eventmessage)
		message = templateobj.render()

 		usertobenotified = User.query.filter_by(reminder="Yes").all()

		for user in usertobenotified:
			print user.email_address
			send_notification(user.email_address,Eventadd,message)
 		
		print message
		create_event(event_name,event_date,event_description)
 		# print eventmessage

 		# print ('before sending email template email')

		print "I am here ********************************************"
	
		return "The event is updated"

	else:

		change_event = Event.query.get(event_id)
		change_event.event_id = event_id
		change_event.event_name=event_name
		change_event.event_date=datetime.strptime(event_date , '%Y-%m-%d')
		change_event.event_length=1
		change_event.event_description=event_description
		change_event.event_status=event_status
		change_event.no_of_spots=event_spots
		change_event.recurring = 'Yes'
		change_event.created_id = 500

		#admin_event = Event(event_id = event_id,event_name=event_name,event_date=datetime.now(),event_length=1,event_description=event_description,event_status=event_status,no_of_spots=event_spots,recurring = 'Yes', created_id=500)
		#db.session.add(admin_event)
		db.session.commit()
		# print event_id , event_name,event_date,event_description,event_status,event_spots
		return "The event is updated"

@app.route("/sign_out")
def logout():
    """ LOGOUT."""
    if "user_id" in session: 
        session.pop('user_id', None)
        flash('You have logged out successfully')
        return render_template('login.html')
    else: 
        #flash('Are you sure you logged in?')
        return render_template('login.html')
      
@app.route("/sign_up" , methods=['POST'])
def usersignup():
	# print "I am in the sign up page"
	""" User input details to populate the user profile page"""
	first_name = request.form.get('fname')
	last_name = request.form.get('lname')
	email_address = request.form.get('email')
	password = request.form.get('password')
	user_address = request.form.get('address')
	phone_number = request.form.get('phone')
	role = request.form.get('role')
	email_reminder = request.form.get('email_reminder')
	user_count = User.query.filter_by(email_address=email_address).count()

	# print role
	# print email_reminder
	# print user_address

	if user_count != 0 :
		flash("Looks an email_address with your name already exists")
		return render_template("login.html")
	else:
		#flash("Please signup for an account")
		# Inserting a new user record into users table 
		new_user = User(password=password, first_name=first_name,last_name=last_name,user_type='User',role=role,reminder=email_reminder,email_address=email_address,phone_number=phone_number ,status='Active', user_address=user_address)		
		db.session.add(new_user)		
		db.session.commit()	
		#
		new_user = User.query.filter_by(email_address=email_address).one()
		return render_template("user_profile.html",new_user=new_user)

@app.route("/signup_page")
def signup_page():
	return render_template('signup.html')

@app.route("/school_events")
def school_events():
	return render_template('school_events.html',first_name=session["first_name"],last_name=session["last_name"])


@app.route("/survey_feedback")
def survey_feedback():
	# print "I am in feedback"
	# Calling sm api to get responses for the survey on the welcome page
	feedback = get_sm_survey_response(68255536)
	return render_template('feedback.html', first_name=session["first_name"],last_name=session["last_name"], feedback = feedback)


#This is the route to delete an event by admin
@app.route('/admin_event_delete', methods=['POST'])
def event_delete():
	print "I am here"
	emailtobenotified=""
	event_id = request.form['eventid']
	print event_id
	event_tobe_deleted = Event.query.filter_by(event_id=event_id).one()
	event_tobe_deleted.event_status = "Deleted"
	registration_tobe_deleted = db.session.query(Registration.registration_id,Registration.event_id,Registration.parent_id,User.email_address).join(User).filter(Registration.event_id==event_id,Registration.status != 'Cancelled').all()	
	if not registration_tobe_deleted:
		print "No registration for this event"
	else:
		registrationdelete = db.session.query(Registration).filter(Registration.event_id==event_id,Registration.status != 'Cancelled').all()
		for regi in registration_tobe_deleted:
			registration = Registration.query.get(regi.registration_id)
			registration.status ="Deleted"
			emailtobenotified+= regi.email_address
			print emailtobenotified
			eventmessage = {}
			eventmessage['eventname'] = event_tobe_deleted.event_name
			eventmessage['eventdate'] = event_tobe_deleted.event_date.strftime("%B %d, %Y")
			eventmessage['eventdesc'] = event_tobe_deleted.event_description
 		
 		# print eventmessage

 		# print ('before sending email template email')

			templateobj = EmailTemplate(template_name='cancellation.txt', values=eventmessage)
			message = templateobj.render()
			print "I am here ********************************************"
			send_notification(regi.email_address,registerDelete,message)
	
	db.session.commit()

	event_record = Event.query.filter_by(event_id=event_id).one()

	print "Reached till here #################################"
	return jsonify(eventid = event_record.event_id,eventstatus =event_record.event_status  )

if __name__ == "__main__":
    # We have to set debug=True here, since it has to be True at the pointyu	q
    # that we invoke the DebugToolbarExtension
    app.debug = False

    connect_to_db(app)

    # Use the DebugToolbar
    DebugToolbarExtension(app)
    registerSub = "Your Registration is Successful"
    registerCancel = "Your Registration is Cancelled"
    registerDelete = "The Event is Cancelled"
    EventChange = "Please note change in your registered event"
    Eventadd = "Please note change a new event is added"
    Eventdelete = "Please note this event is deleted"


    app.run()    
