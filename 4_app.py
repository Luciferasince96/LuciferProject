from datetime import date
birth_year = input ("Enter you birth year: ")
age = date.today().year - int(birth_year)
print(age)