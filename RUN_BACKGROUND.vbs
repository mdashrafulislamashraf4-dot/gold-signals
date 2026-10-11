Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Ashraful Islam\Desktop\Ai signals"
WshShell.Run """C:\Users\Ashraful Islam\AppData\Local\Programs\Python\Python312\python.exe"" main.py", 0, False
