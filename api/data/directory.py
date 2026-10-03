"""Paytm's accounts, as far as the demo needs them. Synthetic.

BAHI never holds a phone number: the shopkeeper types one, Paytm finds the
account, and the number is thrown away. We don't have Paytm's user system, so
this file stands in for its lookup. Every number and UPI ID here is made up.

Rukhsana is the seed's invitation (data/personas.py): she was invited by number
yesterday and hasn't said yes. Kavita and Tushar are on Paytm and in nobody's
book yet, so an invite can be tried live. Sharma is already in the book.
"""

from __future__ import annotations

from dataclasses import dataclass

from data.world import uid


@dataclass(frozen=True, slots=True)
class Account:
    person_id: str
    name: str
    phone: str
    upi: str


ACCOUNTS: tuple[Account, ...] = (
    Account(
        str(uid("person", "rukhsana")), "Rukhsana Shaikh", "9876543210", "rukhsana@ptys"
    ),
    Account(
        str(uid("person", "kavita")), "Kavita Rao", "9820011223", "kavita.rao@ptaxis"
    ),
    Account(str(uid("person", "tushar")), "Tushar Pawar", "9867044556", "tushar@pthdfc"),
    Account(
        str(uid("person", "sharma")), "Rakesh Sharma", "9819019019", "sharma19@ptsbi"
    ),
)


#: The name on each seeded person's Paytm account, by the name the shop gave
#: them. A shop says "Iqbal bhai" or "Mishra ji"; Paytm has the full name. Made
#: up, like everything here.
REAL_NAMES: dict[str, str] = {
    "Anil": "Anil Tiwari",
    "Ansari": "Salim Ansari",
    "Anubhav": "Anubhav Shukla",
    "Anubhav Jain": "Anubhav Jain",
    "Anubhav Shukla": "Anubhav Shukla",
    "Asha": "Asha Kale",
    "Babu": "Babu Rao Patil",
    "Bhosale": "Ganesh Bhosale",
    "Chavan": "Prakash Chavan",
    "D'Souza": "Joseph D'Souza",
    "Deshmukh": "Vinod Deshmukh",
    "Farah": "Farah Siddiqui",
    "Farida": "Farida Sayyed",
    "Fernandes": "Maria Fernandes",
    "Gaikwad": "Sunil Gaikwad",
    "Ganesh": "Ganesh Kamble",
    "Imran": "Imran Shaikh",
    "Iqbal bhai": "Iqbal Qureshi",
    "Jadhav": "Rohit Jadhav",
    "Joshi kaka": "Madhukar Joshi",
    "Kadam": "Santosh Kadam",
    "Kamat": "Ravi Kamat",
    "Kamla behen": "Kamla Devi",
    "Khan": "Aslam Khan",
    "Lata": "Lata Pawar",
    "Lobo": "Peter Lobo",
    "Meena Tai": "Meena Salvi",
    "Mhatre": "Dilip Mhatre",
    "Mishra ji": "Ramesh Mishra",
    "More": "Nitin More",
    "Naik": "Sanjay Naik",
    "Nazia": "Nazia Khan",
    "Nikhil": "Nikhil Rane",
    "Pandey": "Ashok Pandey",
    "Patil": "Vijay Patil",
    "Pawar": "Ajay Pawar",
    "Pinto aunty": "Lucy Pinto",
    "Qureshi": "Yusuf Qureshi",
    "Rahul": "Rahul Yadav",
    "Raju": "Raju Gaikwad",
    "Rane": "Mahesh Rane",
    "Rekha": "Rekha Sawant",
    "Rizwan": "Rizwan Ahmed",
    "Salma": "Salma Begum",
    "Salunkhe": "Anil Salunkhe",
    "Shaikh bhai": "Rafiq Shaikh",
    "Sharma": "Rakesh Sharma",
    "Sharma ji": "Rakesh Sharma",
    "Shetty": "Suresh Shetty",
    "Shinde": "Kiran Shinde",
    "Sunita": "Sunita Waghmare",
    "Suresh": "Suresh Yadav",
    "Usha": "Usha Kulkarni",
    "Vora": "Hitesh Vora",
    "Wagh": "Deepak Wagh",
    "Yadav": "Ramu Yadav",
    "Zainab": "Zainab Ali",
}
