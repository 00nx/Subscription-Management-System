@echo off
rem Brightloop with a real PostgreSQL 16 server You must install PostgreSQL first.
rem The default launcher, run.cmd, needs no database install.
call "%~dp0run.cmd" --postgres %*
