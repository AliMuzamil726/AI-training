# ============================================================
#   PYTHON QUICK REVIEW — All Topics with Examples
#   Aleena — Emerson University Multan
# ============================================================

# ─────────────────────────────────────────────
# SECTION 1: VARIABLES & DATA TYPES
# ─────────────────────────────────────────────
print("=" * 50)
print("  SECTION 1: VARIABLES & DATA TYPES")
print("=" * 50)

name       = "Aleena"      # str
age        = 21            # int
gpa        = 3.8           # float
is_student = True          # bool
nothing    = None          # NoneType

print(type(name))          # <class 'str'>
print(type(age))           # <class 'int'>
print(type(gpa))           # <class 'float'>
print(type(is_student))    # <class 'bool'>

# Type Conversion
print(int("42"))           # → 42
print(str(100))            # → '100'
print(float(5))            # → 5.0
print(bool(0))             # → False
print(bool("hello"))       # → True

# Input / Output
# name = input("Apna naam batao: ")  # uncomment to use
print(f"Salam, {name}!")   # f-string

# Arithmetic Operators
print(10 + 3)   # 13
print(10 - 3)   # 7
print(10 * 3)   # 30
print(10 / 3)   # 3.333...
print(10 // 3)  # 3    (floor division)
print(10 % 3)   # 1    (remainder)
print(2 ** 8)   # 256  (power)


# ─────────────────────────────────────────────
# SECTION 2: CONTROL FLOW
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  SECTION 2: CONTROL FLOW")
print("=" * 50)

# If / Elif / Else
marks = 75

if marks >= 90:
    print("A grade")
elif marks >= 70:
    print("B grade")
elif marks >= 50:
    print("C grade")
else:
    print("Fail — mehnat karo!")

# Comparison operators: == != > < >= <=
# Logical operators: and  or  not
x = 10
print(x > 5 and x < 20)   # True
print(x < 5 or x == 10)   # True
print(not (x == 10))       # False

# For Loop
fruits = ["apple", "mango", "banana"]
for f in fruits:
    print(f)

# range()
for i in range(5):          # 0 1 2 3 4
    print(i, end=" ")
print()

for i in range(1, 6):       # 1 2 3 4 5
    print(i, end=" ")
print()

for i in range(0, 10, 2):   # 0 2 4 6 8
    print(i, end=" ")
print()

# While Loop
count = 0
while count < 5:
    print(count, end=" ")
    count += 1
print()

# break & continue
for i in range(10):
    if i == 5:
        break           # 5 par ruk jao
    print(i, end=" ")
print()

for i in range(6):
    if i % 2 == 0:
        continue        # even skip karo
    print(i, end=" ")  # 1 3 5
print()


# ─────────────────────────────────────────────
# SECTION 3: FUNCTIONS
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  SECTION 3: FUNCTIONS")
print("=" * 50)

# Basic function
def greet(name):
    return f"Salam, {name}!"

print(greet("Aleena"))

# Default arguments
def introduce(name, city="Multan"):
    print(f"{name} from {city}")

introduce("Aleena")
introduce("Sara", "Lahore")
introduce(city="Karachi", name="Ali")  # keyword args

# *args — kitne bhi arguments
def add_all(*nums):
    return sum(nums)

print(add_all(1, 2, 3, 4, 5))   # 15

# **kwargs — keyword arguments
def show_info(**info):
    for key, val in info.items():
        print(f"  {key}: {val}")

show_info(name="Aleena", age=21, city="Multan")

# Lambda
square = lambda x: x ** 2
print(square(5))    # 25

add    = lambda a, b: a + b
print(add(3, 7))    # 10

# Sorting with lambda
names = ["Zara", "Ali", "Bina", "Muhammad"]
names.sort(key=lambda n: len(n))  # sort by length
print(names)


# ─────────────────────────────────────────────
# SECTION 4: DATA STRUCTURES
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  SECTION 4: DATA STRUCTURES")
print("=" * 50)

# --- LIST ---
print("\n-- LIST --")
nums = [1, 2, 3, 4, 5]
nums.append(6)          # end mein add
nums.insert(0, 0)       # index 0 pe insert
nums.remove(3)          # value 3 hata do
popped = nums.pop()     # last nikalo
print(nums)
print("Popped:", popped)
print("First:", nums[0])
print("Last:", nums[-1])
print("Slice:", nums[1:4])
nums.sort()
print("Sorted:", nums)
nums.reverse()
print("Reversed:", nums)
print("Length:", len(nums))
print("Is 2 in list?", 2 in nums)

# List Comprehension
squares = [x**2 for x in range(1, 6)]
print("Squares:", squares)          # [1, 4, 9, 16, 25]

evens = [x for x in range(10) if x % 2 == 0]
print("Evens:", evens)              # [0, 2, 4, 6, 8]

# --- TUPLE ---
print("\n-- TUPLE --")
point = (10, 20)
x, y = point           # unpacking
print(f"x={x}, y={y}")

coords = (1, 2, 3, 4, 5)
print("First:", coords[0])
print("Slice:", coords[1:4])
print("Length:", len(coords))
# coords[0] = 99     # ERROR! tuple immutable hai

# --- DICTIONARY ---
print("\n-- DICTIONARY --")
student = {
    "name": "Aleena",
    "age": 21,
    "gpa": 3.8
}

print(student["name"])
print(student.get("city", "N/A"))  # safe access
student["city"] = "Multan"         # add key
del student["age"]                 # delete key
print(student.keys())
print(student.values())

for key, val in student.items():
    print(f"  {key}: {val}")

# Dict comprehension
word_len = {word: len(word) for word in ["apple", "mango", "banana"]}
print(word_len)

# --- SET ---
print("\n-- SET --")
a = {1, 2, 3, 2, 1}    # duplicates auto-remove
b = {2, 3, 4}
print("a:", a)
print("Union a|b:",        a | b)
print("Intersection a&b:", a & b)
print("Difference a-b:",   a - b)
print("Sym Diff a^b:",     a ^ b)


# ─────────────────────────────────────────────
# SECTION 5: STRINGS
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  SECTION 5: STRINGS")
print("=" * 50)

s = "  Hello World  "

print(s.strip())               # "Hello World"
print(s.upper())               # "  HELLO WORLD  "
print(s.lower())               # "  hello world  "
print(s.replace("Hello", "Hi"))
print(s.split())               # ["Hello", "World"]
print(s.find("World"))         # 8
print(s.count("l"))            # 3
print(s.strip().startswith("Hello"))  # True

words = ["Python", "is", "cool"]
print(", ".join(words))        # "Python, is, cool"

# Slicing
s2 = "Python"
print(s2[0])        # 'P'
print(s2[-1])       # 'n'
print(s2[0:3])      # 'Pyt'
print(s2[::-1])     # 'nohtyP'  (reverse)

# f-string formatting
pi = 3.14159
print(f"Pi = {pi:.2f}")       # Pi = 3.14
print(f"Score: {95:>10}")     # right-align 10 chars
print(f"{1000000:,}")         # 1,000,000


# ─────────────────────────────────────────────
# SECTION 6: OOP — Object Oriented Programming
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  SECTION 6: OOP")
print("=" * 50)

# --- Basic Class ---
class Student:
    university = "Emerson University"   # class variable

    def __init__(self, name, age):      # constructor
        self.name = name                # instance variables
        self.age  = age

    def greet(self):
        print(f"Salam! Main {self.name} hoon, age {self.age}")

    def __str__(self):                  # print karo to yeh aata hai
        return f"Student({self.name}, {self.age})"

    def __repr__(self):
        return f"Student(name='{self.name}', age={self.age})"


s1 = Student("Aleena", 21)
s1.greet()
print(s1)
print(Student.university)

# --- Inheritance ---
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        print(f"{self.name}: ...")


class Dog(Animal):
    def speak(self):                    # override
        print(f"{self.name}: Woof!")


class Cat(Animal):
    def speak(self):
        print(f"{self.name}: Meow!")


class PoliceDog(Dog):
    def __init__(self, name, badge):
        super().__init__(name)          # parent ka __init__ call
        self.badge = badge

    def introduce(self):
        print(f"K9 Officer {self.name}, Badge #{self.badge}")


d = Dog("Bruno")
c = Cat("Whiskers")
pd = PoliceDog("Rex", 101)
d.speak()
c.speak()
pd.speak()
pd.introduce()

# Polymorphism
animals = [Dog("Buddy"), Cat("Luna"), Dog("Max")]
for animal in animals:
    animal.speak()   # sab alag alag bolenge

# --- Encapsulation ---
class BankAccount:
    def __init__(self, owner):
        self.owner     = owner
        self.__balance = 0          # private variable

    def deposit(self, amount):
        if amount > 0:
            self.__balance += amount
            print(f"Rs.{amount} deposit hua. Balance: {self.__balance}")

    def withdraw(self, amount):
        if amount > self.__balance:
            print("Insufficient balance!")
        else:
            self.__balance -= amount
            print(f"Rs.{amount} nikaala. Balance: {self.__balance}")

    def get_balance(self):
        return self.__balance


acc = BankAccount("Aleena")
acc.deposit(5000)
acc.withdraw(2000)
acc.withdraw(9999)
print("Final Balance:", acc.get_balance())
# print(acc.__balance)   # AttributeError! private hai


# ─────────────────────────────────────────────
# SECTION 7: FILE HANDLING & EXCEPTIONS
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  SECTION 7: FILE HANDLING & EXCEPTIONS")
print("=" * 50)

# --- Write ---
with open("sample.txt", "w") as f:
    f.write("Pehli line\n")
    f.write("Doosri line\n")
    f.write("Teesri line\n")
print("File likh di!")

# --- Read (puri file) ---
with open("sample.txt", "r") as f:
    content = f.read()
    print("Full file:\n", content)

# --- Read (line by line) ---
with open("sample.txt", "r") as f:
    for line in f:
        print("Line:", line.strip())

# --- Append ---
with open("sample.txt", "a") as f:
    f.write("Chauthi line (append)\n")

# --- Exception Handling ---
# ZeroDivisionError
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Zero se divide nahi hota!")

# ValueError
try:
    num = int("hello")
except ValueError:
    print("Yeh number nahi hai!")

# Full try-except-else-finally
try:
    x = int("42")
    result = 100 / x
except ValueError:
    print("Value error!")
except ZeroDivisionError:
    print("Divide by zero!")
except Exception as e:
    print(f"Koi aur error: {e}")
else:
    print(f"Koi error nahi! Result = {result}")
finally:
    print("Yeh hamesha chalta hai!")

# FileNotFoundError
try:
    with open("nahi_hai.txt", "r") as f:
        data = f.read()
except FileNotFoundError:
    print("File nahi mili!")


# ─────────────────────────────────────────────
# BONUS: USEFUL BUILT-IN FUNCTIONS
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  BONUS: USEFUL BUILT-INS")
print("=" * 50)

nums = [3, 1, 4, 1, 5, 9, 2, 6]
print("max:", max(nums))        # 9
print("min:", min(nums))        # 1
print("sum:", sum(nums))        # 31
print("len:", len(nums))        # 8
print("sorted:", sorted(nums))  # ascending
print("sorted desc:", sorted(nums, reverse=True))

# map / filter
squares = list(map(lambda x: x**2, [1,2,3,4,5]))
print("map squares:", squares)

evens = list(filter(lambda x: x % 2 == 0, range(10)))
print("filter evens:", evens)

# zip
names  = ["Ali", "Sara", "Zara"]
scores = [85, 92, 78]
for name, score in zip(names, scores):
    print(f"  {name}: {score}")

# enumerate
for i, item in enumerate(["a", "b", "c"]):
    print(f"  Index {i}: {item}")


print("\n" + "=" * 50)
print("  Review complete! Ab practice karo 🚀")
print("=" * 50)