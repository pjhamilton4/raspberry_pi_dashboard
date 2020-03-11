#!/usr/bin/python3
## Activity monitor for Raspberry PI's with a small (40x60) LCD screen
## Tested and intended for use on a Raspberry PI 3b with a 480x320px 3.5" TFTLCD screen
### JTC, June 2019

# -*- coding: utf-8 -*-

## Changelog:
# 0.3: First documented version, V0.1 and V0.2 were for learning curses stuffs
##     First parts of updateStaticInfo() (hostname is done)
##     First parts of updateDaily() (updates, wipaddr, lipaddr, interfaces are done)
# 0.4: Fixed updateDaily() apt commands

## This version is a special one, created in March 2020
# Due to the rapid spread of the Corona CoVID-19 virus,
# I have decided it's important enough information to
# Have on my activity monitor
# I won't be removing any original code, but the entire
# 'Services' part of the program has been replaced with
# Information about the Corona virus

import os
import curses
import curses.textpad
import subprocess
import time
import urllib.request
from sys import argv, version_info

### Variables
__version__ = '0.9'
staticvars = {'updateamount': 0, # Amount of updates
        'interval': 5, # updateOften() interval in seconds
        'semi_interval': 10, # updateSemiOften() interval in minutes
        'internet_interval': 4, # Internet speed gets calculated once every X times updateSemiOften() runs
        'internet_count': 4, # The amount of times that updateSemiOften() has ran since calculating
        'nextupdate': 'normal', # The kind of update that's next, can be 'normal' or 'daily'
        'updatemin': 10 # The minutes left until the next update, whether that's 'normal' or 'daily'
        }
                ## Is updated by updateStaticInfo(), updateDaily(), updateSemiOften() and updateOften()
testmode = False ## Enable or disable updates and internet speed, as they halt the startup by about a minute
## Due to updateDaily() and updateSemiOften() needing 'hour' and 'minute', which are updated in the function after it
## updateOften(), retrieve the hour and minute here once
staticvars['hour']   = time.strftime("%H", time.localtime()) 
staticvars['minute'] = time.strftime("%M", time.localtime())
countries = ['Mainland China', 'Italy', 'Netherlands']
coronainfo = {'world_inf': 'ERR',
              'world_dead': 'ERR',
              'nl_inf': 'ERR',
              'nl_dead': 'ERR',
              'cn_inf': 'ERR',
              'cn_dead': 'ERR',
              'it_inf': 'ERR',
              'it_dead': 'ERR'}
### End Variables

### Functions
def updateStaticInfo():
    '''statmon.py updateStaticInfo() documentation:
    Function doesn't take variables.
    Its function is to retrieve any info that shouldn't change while running
    Such as system info and hostname
    This function is to be called at program startup and can be initiated manually by pressing 'shift+u'
    '''
    problem = False
    # Hostname
    hostname = subprocess.run(['hostname'], stdout=subprocess.PIPE)
    hostname = hostname.stdout.decode('utf-8')
    staticvars['hostname'] = hostname.strip()
    
    # OS and Kernel
    kernel = subprocess.run(['uname', '-sr'], stdout=subprocess.PIPE)
    kernel = kernel.stdout.decode('utf-8').strip()
    staticvars['kernel'] = kernel

    # BSSIDs
    eth_bssid  = subprocess.run(['ip', 'addr', 'show', 'eth0'],  stdout=subprocess.PIPE).stdout.decode('utf-8').split('\n')[1]
    wifi_bssid = subprocess.run(['ip', 'addr', 'show', 'wlan0'], stdout=subprocess.PIPE).stdout.decode('utf-8').split('\n')[1]
    eth_bssid = eth_bssid[eth_bssid.find("link")+11:].split(' ')[0].strip()
    wifi_bssid = wifi_bssid[wifi_bssid.find("link")+11:].split(' ')[0].strip()
    staticvars['eth_bssid'] = eth_bssid
    staticvars['wifi_bssid'] = wifi_bssid

    ## End updateStaticInfo(), return True upon completion
    if problem:
        return False
    else:
        return True

def updateDaily():
    '''statmon.py updateDaily() documentation:
    Function doesn't take variables.
    This function is to be called once every day, to check and retrieve updates
    and other tasks that take too long or change too rarely to call every second
    This function is to be called at program startup and can be initiated manually by pressing 'u'
    '''
    problem = False
    global staticvars
    global testmode
    # Updates
    if not testmode:
        ## I'm using the deprecated apt-get commands, because apt reports an unstable CLI, which is not handy for scripts like this one
        subprocess.run(['sudo', 'apt-get', 'update'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) ## Run the apt-get update command to check for updates
        updatelist = subprocess.run(['sudo', 'apt', 'list', '--upgradable'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) ## Run list upgradable to list upgradable packages and read output
        ## Redirect stderr to stdout to keep it from appearing in the program (apt update returns stderr if there is no internet)
        updates = updatelist.stdout.decode('utf-8').split('\n')
        updateamount = 0
        for update in updates:
            if update == '': # If the entire line is empty (the last one will be when splitting with \n) ignore it
                pass
            elif update[0] == 'N': # Sometimes, there are notes in the output which start with 'N'
                pass
            elif update[0] == 'W': # And catch the 'unstable CLI warning' too, while we're at it (doesn't work yet)
                pass
            elif update[0] == 'L': # The first entry of the output is 'Listing...', remove that
                pass
            else:
                updateamount += 1
        staticvars['updateamount'] = updateamount
    else:
        staticvars['updateamount'] = 'DISABLED'

    # Save the time at which this was updated
    staticvars['daily_update_hour'] = staticvars['hour']
    staticvars['daily_update_minute'] = staticvars['minute']

    ## End updateDaily(), return True upon completion
    if problem:
        return False
    else:
        return True

def updateSemiOften():
    '''updateSemiOften(): Documentation
    This function retrieves info that needs to stay up-to-date, but shouldn't be updated
    every few seconds. This function is supposed to be called every 10-15 minutes.
    Data includes: 'pinging google to test internet connection' (don't do that every few seconds)
    'nagging systemd for info about all services' and 'updating IP addresses'
    '''
    problem = False
    global testmode
    #IP
    ## Retrieve interfaces with IP addresses
    ip_ifs = subprocess.run(['ip', '-4', 'addr'], stdout=subprocess.PIPE)
    ip_ifs = ip_ifs.stdout.decode('utf-8').split('\n')
    interfaces = []
    for intf,line in enumerate(ip_ifs):
        if line != '': # There is always a trailing '' at the end of every STDOUT. Thanks to that, line[0] shits itself
            if line[0] != ' ':
                line = line[3:] # Remove the interface number, colon and whitespace of this way-too-verbose piece of garbage command
                line = line[:line.find(":")] # Find the first instance of ":" and remove it and everything behind it
                interfaces.append(line)

    ## WLan IP, only retrieve if connectivity
    if 'wlan0' in interfaces:
        wipaddr = subprocess.run(['ip', '-4', 'addr', 'show', 'wlan0'], stdout=subprocess.PIPE)
        wipaddr = wipaddr.stdout.decode('utf-8')
        wipaddr = wipaddr[wipaddr.find('inet')+5:wipaddr.find('inet')+19] # Only works if the IP is exactly 14 characters long (which it always is with my DHCP shitpile)
        staticvars['wipaddr'] = wipaddr.strip()
    else:
        staticvars['wipaddr'] = 'Not connected'
    ## Eth IP, only retrieve if connectivity
    if 'eth0' in interfaces:
        lipaddr = subprocess.run(['ip', '-4', 'addr', 'show', 'wlan0'], stdout=subprocess.PIPE)
        lipaddr = lipaddr.stdout.decode('utf-8')
        lipaddr = lipaddr[lipaddr.find('inet')+5:lipaddr.find('inet')+19] # Only works if the IP is exactly 14 characters long (which it always is with my DHCP shitpile)
        staticvars['lipaddr'] = lipaddr.strip()
    else:
        staticvars['lipaddr'] = 'Not connected'

    # Internet access
    try:
        if urllib.request.urlopen("https://google.com/").getcode() == 200:
            staticvars['www_access'] = 'Established'
        if urllib.request.urlopen("https://archlinux.org/").getcode() == 200:
            staticvars['www_access'] = 'Established'
    except OSError:
        staticvars['www_access'] = 'Disconnected'
    except urllib.error.URLError:
        staticvars['www_access'] = 'Disconnected'
    except:
        staticvars['www_access'] = 'ERROR'
    else:
        staticvars['www_access'] = 'Established'

    # Internet speed
    if not testmode:
        if staticvars['internet_count'] >= staticvars['internet_interval']:
            staticvars['internet_count'] = 1
            staticvars['speed_up'] = 'ERR'
            staticvars['speed_down'] = 'ERR'
            staticvars['ping'] = 'ERR'
            if staticvars['www_access'] == 'Established':
                try: # if internet access suddenly dies, the program crashes
                    speed = subprocess.run(['speedtest-cli'], stdout=subprocess.PIPE)
                    speed = speed.stdout.decode('utf-8').split("\n")
                    for line in speed:
                        if line.find("Upload:") != -1:
                            staticvars['speed_up'] = line[8:]
                        elif line.find("Download:") != -1:
                            staticvars['speed_down'] = line[10:]
                        elif line.find("Hosted by") != -1:
                            staticvars['ping'] = line[line.find(":")+1:]
                except:
                    pass # DONT DO THE CRASHEROO
        else:
            staticvars['internet_count'] += 1
    else:
        staticvars['speed_up'] = staticvars['speed_down'] = staticvars['ping'] = 'DISABLED'

    # Apache Process status
    ### COMING LATER
    staticvars['apache_stat'] = 'Inactive'

    # SSL service status
    ### COMING LATER
    staticvars['ssl_stat'] = 'Inactive'

    # FTP service status
    ### COMING LATER
    staticvars['ftp_stat'] = 'Inactive'

    # Veldkamp-Mainframe ping
    try:
        urllib.request.urlopen("http://192.168.178.49").getcode()
    except OSError:
        staticvars['vmf_stat'] = 'Offline'
    except urllib.error.URLError:
        staticvars['vmf_stat'] = 'Offline'
    except:
        staticvars['vmf_stat'] = 'ERROR'
    else:
        staticvars['vmf_stat'] = 'Online'

    # Corona info
    if staticvars['www_access'] == 'Established':
        try:
            request = urllib.request.Request("https://corona.help/", headers={'User-Agent': 'Mozilla/5.0'}) # https://corona.help does not like Python, so we give it the finger and call ourself Firefox
            html = urllib.request.urlopen(request).read()
            html = html.decode('utf-8').split('\n')

            lookNext = False
            lookAfterNext = False
            foundInfected = False
            foundDeathcount = False
            firstRound = True
            foundChina = False
            country_string = ""
            for line in html:
                try:
                    if lookNext == True:
                        lookNext = False
                        line = line.strip()
                        if line[:23] == '<td class="text-right">':
                            i = 23
                            number_string = ""
                            while True:
                                if line[i] != '<':
                                    number_string += line[i]
                                    i += 1
                                else:
                                    break
                            if country_string == 'Mainland China':
                                if not foundChina:
                                    foundChina = True
                                    coronainfo['cn_inf'] = number_string
                                else:
                                    firstRound = False
                                    coronainfo['cn_dead'] = number_string
                            elif country_string == 'Italy':
                                if firstRound:
                                    coronainfo['it_inf'] = number_string
                                else:
                                    coronainfo['it_dead'] = number_string
                            elif country_string == 'Netherlands':
                                if firstRound:
                                    coronainfo['nl_inf'] = number_string
                                else:
                                    coronainfo['nl_dead'] = number_string

                    elif lookAfterNext == True: # Skip the next one (probably </td>) and then check
                        lookAfterNext = False
                        lookNext = True

                    elif line.strip()[:6] == '<td><a':
                        # Change the first '>', because we want to find the second one
                        i = line.replace('>', '-', 1).find('>') + 1
                        country_string = ""
                        while True:
                            if line[i] != '<':
                                country_string += line[i]
                                i += 1
                            else:
                                break
                        if country_string in countries:
                            lookAfterNext = True
                    elif line.strip()[:4] == '<h1>': # There are only 3 lines in the document with the first header
                        number_string = ""
                        line = line.strip()
                        i = 4
                        while True:
                            if line[i] != '<':
                                number_string += line[i]
                                i += 1
                            else:
                                break
                        if not foundInfected:
                            foundInfected = True
                            coronainfo['world_inf'] = number_string
                        else:
                            if not foundDeathcount:
                                foundDeathcount = True
                                coronainfo['world_dead'] = number_string
                except Exception as e: ## If somehow this throws an error, we don't need the line anyway
                    pass
        except:
            for key in coronainfo.keys():
                coronainfo[key] = 'ERR'

    # Save the time at which this was updated
    staticvars['semi_update_hour'] = staticvars['hour']
    staticvars['semi_update_minute'] = staticvars['minute']

    ## End updateSemiOften(), return True upon successful completion
    if problem:
        return False
    else:
        return True

def updateOften():
    '''updateOften(): Documentation
    This retrieves the info that's updated every few seconds.
    I didn't plan to make this a function, but it is going to look a lot cleaner
    in the function that prints everything to the screen.'''
    problem = False
    # Uptime
    uptime = subprocess.run(['uptime', '-p'], stdout=subprocess.PIPE)
    uptime = uptime.stdout.decode('utf-8').strip()
    staticvars['uptime'] = uptime[3:] # Output is 'up x hours, xx minutes' - remove the 'up '

    # Processes
    processlist = subprocess.run(['ps', '-A'], stdout=subprocess.PIPE)
    processlist = processlist.stdout.decode('utf-8').split('\n')
    staticvars['processes'] = len(processlist) -1

    # CPU Temp
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as cputempfile:
        cputemp = cputempfile.read()
    cputemp = cputemp.strip()
    try:
        cputemp = round(int(cputemp) / 1000, 1)
    except ValueError:
        cputemp = 'ERR'
    staticvars['cputemp'] = cputemp

    # Memory
    staticvars['total_mem'], staticvars['used_mem'] = map(int, os.popen('free -t -m').readlines()[1].split()[1:3])

    # Signal strength internet/wifi
    if staticvars['wipaddr'] != 'Not connected':
        try:
            staticvars['essid'] = staticvars['sig_pow'] = staticvars['sig_qua'] = 'ERROR'
            iw_output = subprocess.run(['iwconfig', 'wlan0'], stdout=subprocess.PIPE)
            iw_output = iw_output.stdout.decode('utf-8').split('\n')
            staticvars['essid'] = iw_output[0][iw_output[0].find("ESSID") + 7:].strip().strip('"')
            staticvars['sig_pow'] = iw_output[5][iw_output[5].find("Signal level") + 13:].strip()
            signal_qual = iw_output[5][iw_output[5].find("Quality")+8:iw_output[5].find("70")-1]
            signal_percentage = int(signal_qual) * 10 / 7
            staticvars['sig_qua'] = str(int(round(signal_percentage,0))) + '%'
        except:
            pass # Don't crash when the internet suddenly dies
    else:
        staticvars['sig_pow'] = staticvars['sig_qua'] = 'N/A' 
        staticvars['essid'] = 'Nothing'

    # Time
    staticvars['hour'] = time.strftime("%H", time.localtime())
    staticvars['minute'] = time.strftime("%M", time.localtime())

    if problem:
        return False
    else:
        return True

def main(monitor): ## Main function
    '''statmon.py main(monitor) documentation:
    Function takes one set variable, do not change this.
    This function is to be initiated from the curses.wrapper() function.
    This function is the main program.
    '''
    monitor.clear()
    # Curses setup
    curses.noecho() # Necessary for reading key inputs
    curses.cbreak() # Don't wait for enter after keystroke
    monitor.keypad(True) # Let curses handle escape sequences
   
    # Startup functions
    pause = False
    monitor.addstr(1,0,10*' ' + " > > > > > RPI Status Monitor < < < < < " + 10*' ', curses.A_BOLD)
    monitor.addstr(4,0,">>> Running updateStaticInfo()... ")
    monitor.refresh()
    ok = updateStaticInfo()
    if ok:
        monitor.addstr("SUCCESS")
    else:
        pause = True
        monitor.addstr("FAILURE")
    monitor.addstr(6,0,">>> Running updateDaily()... ")
    monitor.refresh()
    ok = updateDaily()
    if ok:
        monitor.addstr("SUCCESS")
    else:
        pause = True
        monitor.addstr("FAILURE")
    monitor.addstr(8,0,">>> Running updateSemiOften()... ")
    monitor.refresh()
    ok = updateSemiOften()
    if ok:
        monitor.addstr("SUCCESS")
    else:
        pause = True
        monitor.addstr("FAILURE")
    monitor.addstr(10,0,">>> Running updateOften()... ")
    monitor.refresh()
    ok = updateOften()
    if ok:
        monitor.addstr("SUCCESS")
    else:
        pause = True
        monitor.addstr("FAILURE")
    monitor.refresh()
    # Initialising colours
    monitor.addstr(12,0,">>> Initialising terminal colours... ")
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
    monitor.addstr("DONE")
    # End Startup functions
    if pause:
        monitor.addstr(37,0,">>> Warning: error detected while executing one or more")
        monitor.addstr(38,0,"functions. Press any key to continue")
        monitor.getkey()
    monitor.clear()

    # Turn off the cursor (visibility)
    curses.curs_set(0)

    # Drawing the screen
    uiDrawer(monitor)
    dataWriter(monitor, updateall=True)
    monitor.refresh()

    # Main program loop
    ## Turn off waiting for keypress
    monitor.nodelay(True)
    while True:
        ## Sleep for the duration of the interval
        curses.napms(1000*staticvars['interval'])
        ## Add a little indication of when it's updating
        monitor.addstr(0,29,"::", curses.color_pair(3) | curses.A_STANDOUT)
        ## Check for keypress
        input_found = False
        while True:                             #> Loop through STDIN until there's nothing left
            try:                                #> and overwrite pressed_key every time there is input
                pressed_key = monitor.getkey()  #> This way, we get the key that's pressed LAST
            except curses.error:                #> Allowing you to change your input after having pressed
                if not input_found:             #> some other key
                    pressed_key = None          #> If you don't do this, if you smash the keyboard, your keypresses
                break                           #> Are handled. One. by. one. by. one. by. one. VERY SLOWLY (time of interval)
            else:
                input_found = True
        
        ## Firstly, input handling
        restore = ud_daily = ud_semi = ud_static = False
        if pressed_key != None:
            monitor.addstr(0,1,'Input: ' + str(pressed_key))
            monitor.refresh()
        if pressed_key == 'u': ## Force update something
            ### Brings up submenu
            restore = True

            submenu = curses.newwin(14,48,13,6)
            try:
                submenu.addstr(0,0,"+" + 46*'-' + "+", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(0,17," Force Update ", curses.A_BOLD | curses.color_pair(4))
                submenu.addstr(13,0,"+" + 46*'-' + "+", curses.A_STANDOUT | curses.color_pair(4))
            except curses.error:
                pass
            for i in range(1,13):
                submenu.addstr(i,0,"|", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(i,47,"|", curses.A_STANDOUT | curses.color_pair(4))
            submenu.addstr(2,2,"Which data group would you like to update?")
            submenu.addstr(3,2,"1) SemiOften (updated every 15 minutes)")
            submenu.addstr(4,2,"  >IPs, Internet access, service statusses")
            submenu.addstr(5,2,"2) Daily (updated daily)")
            submenu.addstr(6,2,"  >OS Updates")
            submenu.addstr(7,2,"3) Static (updated at program startup)")
            submenu.addstr(8,2,"  >Hostname, OS, Kernel, BSSIDs")
            submenu.addstr(9,2,"4) All")
            submenu.addstr(11,2,"Please enter the number of the update group")
            submenu.refresh()

            ### Wait until input
            #submenu.nodelay(False)
            selection = submenu.getch()
            if selection == ord('1'):
                ud_semi = True
            elif selection == ord('2'):
                ud_daily = True
            elif selection == ord('3'):
                ud_static = True
            elif selection == ord('4'):
                ud_semi = ud_daily = ud_static = True

        elif pressed_key == 'U': ## Force update all
            ud_daily = ud_semi = ud_static = True

        elif pressed_key == 'h': ## Bring up help screen
            ### Brings up submenu
            restore = True
            
            submenu = curses.newwin(16, 48, 12, 6)
            try: # Curses throws an error when drawing the last character of a window, as the cursor has no place to go
                submenu.addstr(0,0,"+" + 46* '-' + "+", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(0,18," Help Menu ", curses.A_BOLD | curses.color_pair(4))
                submenu.addstr(15,0,"+" + 46* '-' + "+", curses.A_STANDOUT | curses.color_pair(4))
            except curses.error: # We're catching that error and ignoring the hell out of it
                pass
            for i in range(1,15):
                submenu.addstr(i,0,"|", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(i,47,"|", curses.A_STANDOUT | curses.color_pair(4))
            submenu.addstr(2,2,"Press 'q' or 'x' to exit the program")
            submenu.addstr(3,2,"Press 'h' to bring up this menu")
            submenu.addstr(4,2,"Press 'i' to set the refresh interval")
            submenu.addstr(5,2,"Press 'v' to see program info and version")
            submenu.addstr(6,2,"Press 'u' to update a data group")
            submenu.addstr(7,2,"Press 'U' to update all data")
            submenu.addstr(8,2,"Press 'd' to redraw the entire screen")
            submenu.addstr(9,2,"Press 't' to see and use test functions")
            submenu.addstr(11,2,"Pressing any of these keys now does nothing")
            submenu.addstr(12,2,"Press any key to close this box, the press")
            submenu.addstr(13,2,"the key you want")
            submenu.refresh()

            ### Wait until keypress
            #submenu.nodelay(False)
            submenu.getkey()

        elif pressed_key in ('q', 'x'): ## Exit
            monitor.clear()
            monitor.addstr(16,8,"  _____                 _ _                ", curses.A_BOLD)
            monitor.addstr(17,8," / ____|               | | |               ", curses.A_BOLD)
            monitor.addstr(18,8,"| |  __  ___   ___   __| | |__  _   _  ___ ", curses.A_BOLD)
            monitor.addstr(19,8,"| | |_ |/ _ \\ / _ \\ / _` | '_ \\| | | |/ _ \\", curses.A_BOLD)
            monitor.addstr(20,8,"| |__| _ (_) | (_) | (_| | |_) | |_| |  __/", curses.A_BOLD)
            monitor.addstr(21,8," \\_____|\\___/ \\___/ \\__,_|_.__/ \\__, |\\___|", curses.A_BOLD)
            monitor.addstr(22,8,"                                 __/ |     ", curses.A_BOLD)
            monitor.addstr(23,8,"                                |___/     ", curses.A_BOLD)
            monitor.refresh()
            time.sleep(1)
            return False

        elif pressed_key == 'i': ## Set interval
            ### Brings up submenu
            restore = True

            submenu = curses.newwin(24, 46, 8, 7)
            interval_container =          curses.newwin(1, 3, 14, 19)
            semi_interval_container =     curses.newwin(1, 5, 19, 24)
            internet_interval_container = curses.newwin(1, 2, 24, 20)
            try:
                submenu.addstr(0,0, "+" + 44 * '-' + "+", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(0,18," Interval ", curses.A_BOLD | curses.color_pair(4))
                submenu.addstr(23,0, "+" + 44 * '-' + "+", curses.A_STANDOUT | curses.color_pair(4))
            except curses.error:
                pass
            for i in range(1,23):
                submenu.addstr(i,0,"|", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(i,45,"|", curses.A_STANDOUT | curses.color_pair(4))
            submenu.addstr( 2,2,"Set new update interval in seconds.")
            submenu.addstr( 3,2,"Current: {}s | Min: 1 - Max: 59".format(staticvars['interval']))
            submenu.addstr( 4,2,"Warning!", curses.A_BOLD)
            submenu.addstr(" Input is read ")
            submenu.addstr("ONCE", curses.A_BOLD)
            submenu.addstr(" every interval")
            submenu.addstr( 6,2,"Interval: __ seconds")
            submenu.addstr( 8,2,"Set new updateSemi() interval in minutes.")
            submenu.addstr( 9,2,"Current: {}m | Min: 1 - Max: 1420".format(staticvars['semi_interval']))
            submenu.addstr(11,2,"Semi Interval: ____ minutes")
            submenu.addstr(13,2,"Set when internet speed is calculated")
            submenu.addstr(14,2,"Current: once every {0} time(s)".format(staticvars['internet_interval']))
            submenu.addstr(16,2,"Once every _ time(s) updateSemi() runs.")
            submenu.addstr(18,2,"Input starts at first field, press enter")
            submenu.addstr(19,2,"to select next field. Leave empty to keep")
            submenu.addstr(20,2,"old value. Press 'c' to cancel without")
            submenu.addstr(21,2,"saving. Press 's' to save changes.")
            submenu.refresh()

            ### Input
            stop = False
            curses.curs_set(1) # Make the cursor visible again
            ## Normal
            textbox = curses.textpad.Textbox(interval_container)
            textbox.edit()
            check_interval = textbox.gather()
            if check_interval == 'c':
                stop = True
            
            ## Semi
            if not stop:
                textbox = curses.textpad.Textbox(semi_interval_container)
                textbox.edit()
                check_semi_interval = textbox.gather()
                if check_semi_interval == 'c':
                    stop = True

            ## Internet
            if not stop:
                textbox = curses.textpad.Textbox(internet_interval_container)
                textbox.edit()
                check_internet_interval = textbox.gather()
                if check_internet_interval == 'c':
                    stop = True

            ## Input checking
            if not stop:
                normal_change = semi_change = internet_change = False
                # Normal
                try:
                    int(check_interval)
                except ValueError:
                    pass
                else:
                    if int(check_interval) > 0 and int(check_interval) < 60:
                        old_interval = staticvars['interval']
                        staticvars['interval'] = int(check_interval)
                        normal_change = True
    
                try:
                    int(check_semi_interval)
                except ValueError:
                    pass
                else:
                    if int(check_semi_interval) > 0 and int(check_interval) < 1421:
                        old_semi_interval = staticvars['semi_interval']
                        staticvars['semi_interval'] = int(check_semi_interval)
                        semi_change = True
    
                try:
                    int(check_internet_interval)
                except ValueError:
                    pass
                else:
                    if int(check_internet_interval) > 0 and int(check_internet_interval) < 10:
                        old_internet_interval = staticvars['internet_interval']
                        staticvars['internet_interval'] = int(check_internet_interval)
                        internet_change = True
    
                changes = 0
                for thingy in (normal_change, semi_change, internet_change):
                    if thingy == True:
                        changes +=1
                
                if changes > 0:
                    height = changes + 6
                    if changes == 2:
                        message = curses.newwin(height, 42, int((40-height)/2), 9)
                    else:
                        message = curses.newwin(height, 42, int((39-height)/2), 9)
                    
                    try:
                        message.addstr(0,0,"+" + 40* '-' + "+", curses.color_pair(4) | curses.A_STANDOUT)
                        message.addstr(0,10," Interval Value Check ", curses.color_pair(4))
                        message.addstr(height-1,0,"+" + 40* '-' + "+", curses.color_pair(4) | curses.A_STANDOUT)
                    except curses.error:
                        pass

                    for i in range(1,height-1):
                        message.addstr(i,0,"|", curses.color_pair(4) | curses.A_STANDOUT)
                        message.addstr(i,41,"|", curses.color_pair(4) | curses.A_STANDOUT)

                    message.move(2,2)
                    if normal_change:
                        message.addstr("Changed update interval from {} to {}".format(old_interval, staticvars['interval']))
                        message.move(message.getyx()[0]+1,2)
                    if semi_change:
                        message.addstr("Changed semi interval from {} to {}".format(old_semi_interval, staticvars['semi_interval']))
                        message.move(message.getyx()[0]+1,2)
                    if internet_change:
                        message.addstr("Changed internet interval from {} to {}".format(old_internet_interval, staticvars['internet_interval']))

                    message.addstr(changes+3,2,"Press 'c' to cancel, press 's' to save")

                    while True:
                        ivc_action = message.getkey()
                        if ivc_action == 'c':
                            staticvars['interval'] = old_interval
                            staticvars['semi_interval'] = old_semi_interval
                            staticvars['internet_interval'] = old_internet_interval
                            stop = True
                            break
                        elif ivc_action == 's':
                            break

                else:
                    message = curses.newwin(6,22,17,19)
                    try:
                        message.addstr(0,0,"+" * 22, curses.color_pair(4) | curses.A_STANDOUT)
                        message.addstr(0,1," Interval Value Check ", curses.color_pair(4))
                        message.addstr(5,0,"+" + '-' * 20 + "+", curses.color_pair(4) | curses.A_STANDOUT)
                    except curses.error:
                        pass
                    for i in range(1,5):
                        message.addstr(i,0,"|", curses.color_pair(4) | curses.A_STANDOUT)
                        message.addstr(i,21,"|", curses.color_pair(4) | curses.A_STANDOUT)
                    message.addstr(2,2,"No changes were made")
                    message.addstr(3,3,"Returning to home")
                    message.refresh()
                    curses.napms(1000)

            if changes > 0:
                if stop:
                    ### Cancel message
                    popup = curses.newwin(5,12,17,24)
                    try:
                        popup.addstr(0,0,"+" + 10*'-' + "+", curses.color_pair(1) | curses.A_STANDOUT)
                        popup.addstr(4,0,"+" + 10*'-' + "+", curses.color_pair(1) | curses.A_STANDOUT)
                    except curses.error:
                        pass
                    for i in range(1,4):
                        popup.addstr(i,0,"|", curses.color_pair(1) | curses.A_STANDOUT)
                        popup.addstr(i,11,"|", curses.color_pair(1) | curses.A_STANDOUT)
    
                    popup.addstr(2,2,"CANCELED", curses.color_pair(1) | curses.A_STANDOUT)
                    popup.refresh()
                    curses.napms(1200)
    
                else:
                    ### Saved message
                    popup = curses.newwin(5,18,17,21)
                    try:
                        popup.addstr(0,0,"+" + 16*'-' + "+", curses.color_pair(2) | curses.A_STANDOUT)
                        popup.addstr(4,0,"+" + 16*'-' + "+", curses.color_pair(2) | curses.A_STANDOUT)
                    except curses.error:
                        pass
                    for i in range(1,4):
                        popup.addstr(i,0,"|", curses.color_pair(2) | curses.A_STANDOUT)
                        popup.addstr(i,17,"|", curses.color_pair(2) | curses.A_STANDOUT)
    
                    popup.addstr(2,2,"CHANGES  SAVED", curses.color_pair(2) | curses.A_STANDOUT)
                    popup.refresh()
                    curses.napms(1200)

            curses.curs_set(0) # Make the cursor invisible
                    
        elif pressed_key == 'v': ## Program info and version
            ### Brings up submenu
            restore = True

            submenu = curses.newwin(18,52,11,4)
            try:
                submenu.addstr( 0,0,"+" + 50 * '-' + "+", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(0,13," Program Info and Version ", curses.color_pair(4))
                submenu.addstr(17,0,"+" + 50 * '-' + "+", curses.A_STANDOUT | curses.color_pair(4))
            except curses.error:
                pass
            for i in range(1,17):
                submenu.addstr(i,0,"|", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(i,51,"|", curses.A_STANDOUT | curses.color_pair(4))
            submenu.addstr(2,2,"Raspberry PI Status Monitor V")
            submenu.addstr(__version__, curses.A_BOLD | curses.color_pair(4))
            submenu.addstr(3,2,"Created by ")
            submenu.addstr("JTC", curses.color_pair(3))
            submenu.addstr(", June-July 2019")
            submenu.addstr(4,2,"Made for a small GPIO touch screen (60x40 chars)")
            submenu.addstr(5,2,"480x320px SPI TFTLCD, mouse/touch not supported")
            submenu.addstr(6,2,"Tested on a Raspberry PI 3b - Raspbian 9 CLI")
            submenu.addstr(7,2,"Written in Python 3.7.3 on Arch Linux")
            submenu.addstr(8,2,"Current Python version: " + str(version_info[0]) + '.' + str(version_info[1]) + '.' + str(version_info[2]))
            submenu.addstr(10,2,"This software is completely free to use, modify")
            submenu.addstr(11,2,"copy, distribute or do whatever else with.")
            submenu.addstr(12,2,"Though it might be too specialised to be of")
            submenu.addstr(13,2,"much use, you can do with it as you please.")
            submenu.addstr(14,2,"If you do use (parts of) this program,")
            submenu.addstr(15,2,"a shoutout is appreciated, but not mandatory.")
            submenu.refresh()

            ### Wait for keypress
            #submenu.nodelay(False)
            submenu.getkey()
        elif pressed_key == 'd': ## Redraw screen
            monitor.clear()
            uiDrawer(monitor)
            dataWriter(monitor, updateall=True)
        elif pressed_key == 't': ## Test functions
            ### Brings up submenu
            restore = True

            submenu = curses.newwin(12,36,14,12)
            try:
                submenu.addstr(0,0,"+" + 34 * "-" + "+", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(0,10," Test Functions ", curses.A_BOLD | curses.color_pair(4))
                submenu.addstr(11,0,"+" + 34 * "-" + "+", curses.A_STANDOUT | curses.color_pair(4))
            except curses.error:
                pass
            for i in range(1,11):
                submenu.addstr(i,0,"|", curses.A_STANDOUT | curses.color_pair(4))
                submenu.addstr(i,35,"|", curses.A_STANDOUT | curses.color_pair(4))
            submenu.addstr(2,2,"1) testStyle()")
            submenu.addstr(3,2,"  > Prints colours and effects")
            submenu.addstr(4,2,"2) showAllInfo()")
            submenu.addstr(5,2,"  > Shows all info unformatted")
            submenu.addstr(6,2,"3) fillscreen()")
            submenu.addstr(7,2,"  > Fills the screen with chars")
            submenu.addstr(9,2,"Enter the number of the function")
            submenu.refresh()

            ### Wait for input
            #submenu.nodelay(False)
            selection = submenu.getch()
            if selection in (ord('1'), ord('2'), ord('3')):
                monitor.nodelay(False)
            if selection == ord('1'):
                testStyle(monitor)
                monitor.refresh()
                monitor.getkey()
            elif selection == ord('2'):
                showAllInfo(monitor)
                monitor.refresh()
                monitor.getkey()
            elif selection == ord('3'):
                fillscreen(monitor)
                monitor.refresh()
                monitor.getkey()

        monitor.addstr(0,1," " * 20) # Remove the input message
        monitor.refresh()
        if restore:
            monitor.clear()
            monitor.nodelay(True)
            uiDrawer(monitor)
            dataWriter(monitor, updateall=True)
            monitor.refresh()
        if pressed_key != None: ## Clear the 'Input: ' message
            monitor.addstr(0,1, 20*' ')
            monitor.refresh()
        ## Secondly, updating
        ### Check what needs to be updated
        if timeCalculator(staticvars['hour'],staticvars['minute'],staticvars['semi_update_hour'],staticvars['semi_update_minute'],staticvars['semi_interval']):
            ud_semi = True
        if timeCalculator(staticvars['hour'],staticvars['minute'],staticvars['daily_update_hour'],staticvars['daily_update_minute'],1420):
            ud_daily = True
        ### Check what needs to be updated next
        time_till_semi  = timeCalTheSecond(staticvars['hour'], staticvars['minute'], staticvars['semi_update_hour'], staticvars['semi_update_minute'],staticvars['semi_interval'])
        time_till_daily = timeCalTheSecond(staticvars['hour'], staticvars['minute'], staticvars['daily_update_hour'], staticvars['daily_update_minute'],1420)
        if time_till_daily <= time_till_semi:
            staticvars['nextupdate'] = 'daily'
            staticvars['updatemin'] = time_till_daily
        else:
            staticvars['nextupdate'] = 'normal'
            staticvars['updatemin'] = time_till_semi

        ### Updating
        updateOften()
        dataWriter(monitor)
        if ud_semi:
            ud_semi = False
            updateSemiOften()
            dataWriter(monitor, semi_often=True)
        if ud_daily:
            ud_daily = False
            updateDaily()
            dataWriter(monitor, daily=True)
        if ud_static:
            ud_static = False
            updateStaticInfo()
            dataWriter(monitor, updateall=True)
        
        ## Remove the indication after updating is complete
        monitor.addstr(0,29,"::", curses.color_pair(3))
        monitor.refresh()

    # Testing
    #fillscreen(monitor)
    #showAllInfo(monitor)
    #uiDrawer(monitor)
    #dataWriter(monitor, updateall=True)
    #testStyle(monitor)

    monitor.refresh()
    monitor.getkey()

def uiDrawer(monitor):
    '''uiDrawer(monitor): Documentation
    This functions writes the ASCII icons, created by myself, and other static UI parts, into the screen
    They should be fine with being written once, but pressing 'i' will re-draw them.
    '''
    # Title
    monitor.addstr(1,0," >" * 14 + " || " + "< " * 14, curses.color_pair(6) | curses.A_BOLD)
    monitor.addstr(2,1," >" * 5 + 38 * ' ' + "< " * 5, curses.color_pair(6) | curses.A_BOLD)
    monitor.addstr(2,12,"Raspberry PI - Activity Monitor V", curses.color_pair(5))
    monitor.addstr(str(__version__), curses.color_pair(5) | curses.A_BOLD)

    # Corona virus special edition
    monitor.addstr(3,31,"CORONA VIRUS SPECIAL EDITION", curses.color_pair(1))

    # Borders
    monitor.addstr( 4,1,"-=-=-" + 20 * ' ' + 16 * '-=' + '-')
    monitor.addstr(18,1,"-=-=-" + 16 * ' ' + 18 * '-=' + '-')
    monitor.addstr(28,1,"-=-=-" + 14 * ' ' + 19 * '-=' + '-')
    monitor.addstr( 4,7,"SYSTEM INFORMATION", curses.A_BOLD)
    monitor.addstr(18,7,"NETWORK STATUS", curses.A_BOLD)
    monitor.addstr(28,7,"CORONA VIRUS", curses.A_BOLD)

    # SYSTEM INFORMATION - ICON
    monitor.addstr( 6,47," *  *#*  * ", curses.color_pair(6))
    monitor.addstr( 7,47,"*** *#* ***", curses.color_pair(6))
    monitor.addstr( 8,47," *#######* ", curses.color_pair(6))
    monitor.addstr( 9,47,"  ##   ##  ", curses.color_pair(6))
    monitor.addstr(10,47,"**# +++ #**", curses.color_pair(6))
    monitor.addstr(11,47,"### + + ###", curses.color_pair(6))
    monitor.addstr(12,47,"**# +++ #**", curses.color_pair(6))
    monitor.addstr(13,47,"  ##   ##  ", curses.color_pair(6))
    monitor.addstr(14,47," *#######* ", curses.color_pair(6))
    monitor.addstr(15,47,"*** *#* ***", curses.color_pair(6))
    monitor.addstr(16,47," *  *#*  * ", curses.color_pair(6))
    ## Change centre colour
    monitor.addstr(10,51,"+++", curses.color_pair(6) | curses.A_STANDOUT)
    monitor.addstr(11,51,"+ +", curses.color_pair(6) | curses.A_STANDOUT)
    monitor.addstr(12,51,"+++", curses.color_pair(6) | curses.A_STANDOUT)
    monitor.addstr(11,52," ", curses.color_pair(0))

    # NETWORK STATUS - ICON
    monitor.addstr(20,48,"//      \\\\", curses.color_pair(4) | curses.A_BOLD)
    monitor.addstr(21,48,"|| /><\\ ||", curses.color_pair(4) | curses.A_BOLD)
    monitor.addstr(22,48,"|| \\></ ||", curses.color_pair(4) | curses.A_BOLD)
    monitor.addstr(23,48,"\\\\  ||  //", curses.color_pair(4) | curses.A_BOLD)
    monitor.addstr(24,48,"    ||", curses.color_pair(4) | curses.A_BOLD)
    monitor.addstr(25,48,"    ||", curses.color_pair(4) | curses.A_BOLD)
    monitor.addstr(26,48,"   /||\\", curses.color_pair(4) | curses.A_BOLD)
    ## Change antennae colour
    monitor.addstr(21,51,"/><\\", curses.color_pair(1))
    monitor.addstr(22,51,"\\></", curses.color_pair(1))

    # CORONA - ICON
    monitor.addstr(30,49,"    #", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(31,49," #  |  #", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(32,49,"  \\>|</", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(33,49,"  ˇ/ \\ˇ", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(34,49,"#--|+|--#", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(35,49,"  ˇ\\_/ˇ", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(36,49,"  />|<\\", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(37,49," #  |  #", curses.color_pair(2) | curses.A_BOLD)
    monitor.addstr(38,49,"    #", curses.color_pair(2) | curses.A_BOLD)
    ## Change 'knobs' colour
    for coord in [[30,53],[31,50],[31,56],[34,49],[34,57],[37,50],[37,56],[38,53]]:
        monitor.addstr(coord[0],coord[1],"#",curses.color_pair(1))
    for coord in [[32,52],[32,54],[33,51],[33,55],[35,51],[35,55],[36,52],[36,54]]:
        monitor.addstr(coord[0],coord[1],"ˇ",curses.color_pair(5)) # The 'ˇ' character is not supported, but instead shows a cube
    monitor.addstr(34,53,"+", curses.color_pair(2) | curses.A_STANDOUT)

def dataWriter(monitor, updateall=False,daily=False,semi_often=False):
    global staticvars

    if updateall:
        daily = True
        semi_often = True

    # OFTEN UPDATES
    ## Time
    monitor.addstr(0,26, str(staticvars['hour']), curses.A_BOLD)
    monitor.addstr(' :: ', curses.color_pair(3))
    monitor.addstr(str(staticvars['minute']), curses.A_BOLD)

    ## Processes
    monitor.addstr(9,1, "Processes: ", curses.A_BOLD)
    monitor.addstr(str(staticvars['processes']) + 5*' ') # From here on out, adding spaces to remove chars if the previous draw was longer
    
    ## CPU Temperature
    monitor.addstr(10,1, "CPU Temperature: ", curses.A_BOLD)
    if staticvars['cputemp'] == 'ERR' or staticvars['cputemp'] > 65.0:
        monitor.addstr(str(staticvars['cputemp']) + u"\N{DEGREE SIGN}" + 'C    ', curses.color_pair(1))
    else:
        monitor.addstr(str(staticvars['cputemp']) + u"\N{DEGREE SIGN}" + 'C    ')

    ## Memory
    monitor.addstr(11,1, "Memory: ", curses.A_BOLD)
    if int(staticvars['used_mem']) / int(staticvars['total_mem']) > 0.8:
        monitor.addstr(str(staticvars['used_mem']) + 'MiB', curses.color_pair(1))
    else:
        monitor.addstr(str(staticvars['used_mem']) + 'MiB')
    monitor.addstr(" / " + str(staticvars['total_mem']) + 'MiB (' + str(round((int(staticvars['used_mem'])/int(staticvars['total_mem']))*100, 1)) + '%)    ')

    ## Uptime
    monitor.addstr(16,1, "Uptime: ", curses.A_BOLD)
    monitor.addstr(staticvars['uptime'] + 10*' ')

    ## Wifi info
    monitor.addstr(24,1, "Connected to: ", curses.A_BOLD)
    monitor.addnstr(staticvars['essid'] + 100*' ', 33)
    monitor.addstr(25,1, "Signal Strength: ", curses.A_BOLD)
    monitor.addstr(str(staticvars['sig_pow']) + 10*' ')
    monitor.addstr(26,1, "Signal Quality :  ", curses.A_BOLD)
    monitor.addstr(staticvars['sig_qua'] + 10*' ')

    ## Refresh interval
    monitor.addstr(38,1,'Refresh Interval: ', curses.A_BOLD)
    monitor.addstr(str(staticvars['interval']) + " seconds     ")

    ## Time till update
    monitor.addstr(39,1,'Next update: ', curses.A_BOLD)
    if staticvars['nextupdate'] == 'daily':
        monitor.addstr('Big update in ' + str(staticvars['updatemin']) + ' minute(s)     ')
    else:
        monitor.addstr('Normal update in ' + str(staticvars['updatemin']) + ' minute(s)     ')

    # SEMI OFTEN UPDATES
    if semi_often:
        ## Internet access
        monitor.addstr(20,1,'Internet Access: ', curses.A_BOLD)
        if staticvars['www_access'] == 'Established':
            monitor.addnstr("Established" + 100*' ', 30, curses.color_pair(2))
        else:
            monitor.addnstr(staticvars['www_access'] + 100*' ', 30, curses.color_pair(1))

        ## Internet speed
        monitor.addstr(21,1,"Approx. speed: ", curses.A_BOLD)
        if not staticvars['www_access'] == 'Established':
            monitor.addnstr('No Internet Access' + 100*' ', 30, curses.color_pair(1) | curses.A_BOLD)
        elif testmode:
            monitor.addnstr('DISABLED' + 100*' ', 30, curses.color_pair(1))
        else:
            monitor.addnstr(u'\N{DOWNWARDS ARROW}' + staticvars['speed_down'] + ' | ' + u'\N{UPWARDS ARROW}' + staticvars['speed_up'] + 100*' ', 30)

        ## IPs
        monitor.addstr(22,1,"LAN IP : ", curses.A_BOLD)
        monitor.addstr(staticvars['lipaddr'] + 13*' ')
        monitor.addstr(23,1,"WLAN IP: ", curses.A_BOLD)
        monitor.addstr(staticvars['wipaddr'] + 13*' ')

        ## Corona virus
        monitor.addstr(30,1,"COUNTRY     | INFECTIONS | DEATHS |", curses.A_BOLD)
        monitor.addstr(31,1,"------------|------------|--------|", curses.A_BOLD)
        monitor.addstr(32,1,"Worldwide   |            |        |", curses.A_BOLD)
        monitor.addstr(33,1,"Netherlands |            |        |", curses.A_BOLD)
        monitor.addstr(34,1,"China       |            |        |", curses.A_BOLD)
        monitor.addstr(35,1,"Italy       |            |        |", curses.A_BOLD)
        monitor.addstr(32,25-len(coronainfo['world_inf']),coronainfo['world_inf'])
        monitor.addstr(33,25-len(coronainfo['nl_inf']),coronainfo['nl_inf'])
        monitor.addstr(34,25-len(coronainfo['cn_inf']),coronainfo['cn_inf'])
        monitor.addstr(35,25-len(coronainfo['it_inf']),coronainfo['it_inf'])
        monitor.addstr(32,34-len(coronainfo['world_dead']),coronainfo['world_dead'])
        monitor.addstr(33,34-len(coronainfo['nl_dead']),coronainfo['nl_dead'])
        monitor.addstr(34,34-len(coronainfo['cn_dead']),coronainfo['cn_dead'])
        monitor.addstr(35,34-len(coronainfo['it_dead']),coronainfo['it_dead'])

        # Mainframe
        #monitor.addstr(36,1,"Veldkamp-Mainframe: ", curses.A_BOLD)
        #monitor.addstr(staticvars['vmf_stat'] + 5*' ', curses.color_pair(1) if staticvars['vmf_stat'] != 'Online' else curses.color_pair(2))

    # DAILY UPDATES
    if daily:
        ## Updates
        monitor.addstr(37,1,"Updates: ", curses.A_BOLD)
        try:
            staticvars['updateamount'] = int(staticvars['updateamount'])
        except ValueError:
            monitor.addstr(str(staticvars['updateamount']), curses.color_pair(1))
        else:
            monitor.addstr(str(staticvars['updateamount']) + 5*' ', curses.A_DIM if staticvars['updateamount'] == 0 else curses.A_BOLD)
    
    # ONE-TIME UPDATES
    if updateall:
        ## hostname
        monitor.addstr(6,1,"Hostname: ", curses.A_BOLD)
        monitor.addstr(staticvars['hostname'])

        ## Kernel
        monitor.addstr(7,1,"Kernel: ", curses.A_BOLD)
        monitor.addstr(staticvars['kernel'])

        ## BSSIDs
        monitor.addstr(13,1,"Eth MAC : ", curses.A_BOLD)
        monitor.addstr(staticvars['eth_bssid'])
        monitor.addstr(14,1,"Wifi MAC: ", curses.A_BOLD)
        monitor.addstr(staticvars['wifi_bssid'])

def testStyle(monitor):
    '''testStyle(monitor): Documentation
    This is a test function, it's sole purpose is for me to check how certain effects show up on screen.'''
    monitor.clear()
    line = 2
    colors = [' #RE#', ' #GR#', ' #YE#', ' #BL#', ' #MG#', ' #CY#', ' #WH#']
    monitor.addstr(line,1,"Blinking text", curses.A_BLINK)
    for num,color in enumerate(colors):
        monitor.addstr(color, curses.color_pair(num+1) | curses.A_BLINK)
    line += 1
    monitor.addstr(line,1,"Bold text", curses.A_BOLD)
    for num,color in enumerate(colors):
        monitor.addstr(color, curses.color_pair(num+1) | curses.A_BOLD)
    line += 1
    monitor.addstr(line,1,"Dim text", curses.A_DIM)
    for num,color in enumerate(colors):
        monitor.addstr(color, curses.color_pair(num+1) | curses.A_DIM)
    line += 1
    monitor.addstr(line,1,"Reverse text", curses.A_REVERSE)
    for num,color in enumerate(colors):
        monitor.addstr(color, curses.color_pair(num+1) | curses.A_REVERSE)
    line += 1
    monitor.addstr(line,1,"Standout text", curses.A_STANDOUT)
    for num,color in enumerate(colors):
        monitor.addstr(color, curses.color_pair(num+1) | curses.A_STANDOUT)
    line += 1
    monitor.addstr(line,1,"Underline text", curses.A_UNDERLINE)
    for num,color in enumerate(colors):
        monitor.addstr(color, curses.color_pair(num+1) | curses.A_UNDERLINE)
    line += 1

def showAllInfo(monitor):
    '''statmon.py showAllInfo(monitor): Documentation
    This is a test function, it's a random collection of all info collected, to check
    whether the info is retrieved and/or formatted correctly.'''
    monitor.clear()
    linenum = 2
    monitor.addstr(linenum,0,"Hostname (hostname): " + str(staticvars['hostname']))
    linenum += 1
    monitor.addstr(linenum,0,"Kernel (kernel): " + str(staticvars['kernel']))
    linenum += 1
    monitor.addstr(linenum,0,"Updates (updateamount): " + str(staticvars['updateamount']))
    linenum += 1
    monitor.addstr(linenum,0,"WLan Address (wipaddr): " + str(staticvars['wipaddr']))
    linenum += 1
    monitor.addstr(linenum,0,"Lan Address (lipaddr):  " + str(staticvars['lipaddr']))
    linenum += 1
    monitor.addstr(linenum,0,"Internet Access (www_access): " + str(staticvars['www_access']))
    linenum += 1
    monitor.addstr(linenum,0,"CPU Temp (cputemp): " + str(staticvars['cputemp']) + u'\N{degree sign}' + 'C')
    linenum += 1
    monitor.addstr(linenum,0,"Processes (processes): " + str(staticvars['processes']))
    linenum += 1
    monitor.addstr(linenum,0,"Uptime (uptime): " + str(staticvars['uptime']))
    linenum += 1
    monitor.addstr(linenum,0,"Signal strength (sig_pow): " + str(staticvars['sig_pow']))
    linenum += 1
    monitor.addstr(linenum,0,"Signal quality (sig_qua): " + str(staticvars['sig_qua']))
    linenum += 1
    monitor.addstr(linenum,0,"ESSID (essid): " + str(staticvars['essid']))
    linenum += 1
    monitor.addstr(linenum,0,"Memory usage (used_mem / total_mem): " + str(staticvars['used_mem']) + 'MiB / ' + str(staticvars['total_mem']) + 'MiB (' + str(round((int(staticvars['used_mem'])*100)/int(staticvars['total_mem']),0)) + '%)')
    linenum += 1
    monitor.addstr(linenum,0,"Current Hour (hour): " + str(staticvars['hour']))
    linenum += 1
    monitor.addstr(linenum,0,"Current Minutes (minute): " + str(staticvars['minute']))
    linenum += 1
    monitor.addstr(linenum,0,"Last SemiOften update hour (semi_update_hour): " + str(staticvars['semi_update_hour']))
    linenum += 1
    monitor.addstr(linenum,0,"Last SemiOften update minutes (semi_update_minute): " + str(staticvars['semi_update_minute']))
    linenum += 1
    monitor.addstr(linenum,0,"Last Daily update hour (daily_update_hour): " + str(staticvars['daily_update_hour']))
    linenum += 1
    monitor.addstr(linenum,0,"Last Daily update minutes (daily_update_minute): " + str(staticvars['daily_update_minute']))
    linenum += 1
    monitor.addstr(linenum,0,"Update interval (interval): " + str(staticvars['interval']))
    linenum += 1
    monitor.addstr(linenum,0,"Type of next update (nextupdate): " + str(staticvars['nextupdate']))
    linenum += 1
    monitor.addstr(linenum,0,"Time till next update (updatemin): " + str(staticvars['updatemin']))
    linenum += 1
    monitor.addstr(linenum,0,"Internet Upload speed (speed_up): " + str(staticvars['speed_up']))
    linenum += 1
    monitor.addstr(linenum,0,"Internet Download speed (speed_down): " + str(staticvars['speed_down']))
    linenum += 1
    monitor.addstr(linenum,0,"Internet Ping (ping): " + str(staticvars['ping']))
    linenum += 1
    monitor.addstr(linenum,0,"Apache Service Status (apache_stat): " + str(staticvars['apache_stat']))
    linenum += 1
    monitor.addstr(linenum,0,"SSL Service Status (ssl_stat): " + str(staticvars['ssl_stat']))
    linenum += 1
    monitor.addstr(linenum,0,"FTP Service Status (ftp_stat): " + str(staticvars['ftp_stat']))
    linenum += 1
    monitor.addstr(linenum,0,"Veldkamp-Mainframe NAS Server reachable? (vmf_stat): " + str(staticvars['vmf_stat']))
    linenum += 1
    monitor.addstr(linenum,0,"Ethernet MAC Address (eth_bssid): " + str(staticvars['eth_bssid']))
    linenum += 1
    monitor.addstr(linenum,0,"Wifi MAC Address (wifi_bssid): " + str(staticvars['wifi_bssid']))
    linenum += 1
    monitor.addstr(linenum,0,"Version (__version__): " + str(__version__))
    linenum += 1
    monitor.addstr(linenum,0,"Testmode (testmode): " + str(testmode))
    
    #monitor.addstr(linenum,0,": " + str(staticvars['']))
    #linenum += 1

def fillscreen(monitor): ## Fill the screen with #, have a border of *
    '''statmon.py fillscreen(monitor) documentation:
    This is a test function, it fills the screen with a 38x58 grid of
    hashtags, with a border of asterisks.'''
    monitor.clear()
    try:
        monitor.addstr(0,0,60*'*')
        for i in range(38):
            monitor.addstr(i+1,0,'*'+58*'#'+'*')
        monitor.addstr(39,0,60*'*')
    except curses.error: ## Because the screen in entirely filled, and the cursor has no space
        pass             ## to go to. This will return as error. Ignore it.
    
def timeCalculator(current_hour, current_min, event_hour, event_min, time_passed):
    '''timeCalculator(current_hour, current_min, event_hour, event_min, time_passed): Documentation
    Sounds a whole lot more impressive than it is. Checks whether a certain time has passed between
    a certain time (event time) and the current time.
    All variables are required, all int. time_passed is given in minutes, one day is 1440 minutes.
    Returns False is time has not passed. Returns True if time has passed. Returns False upon error
    time_passed will need to be less than a day, as this condition will never be met
    Examp: current_time 00:02 (2) and event_time 00:01 (1) yesterday. 1441 minutes have passed, but 2-1 = 1'''
    try:
        current_hour = int(current_hour)
        current_min = int(current_min)
        event_hour = int(event_hour)
        event_min = int(event_min)
        time_passed = int(time_passed)
    except ValueError:
        return False
    current_time = current_hour * 60 + current_min
    event_time = event_hour * 60 + event_min
    if current_time < event_time:
        current_time += 1440
    if current_time - event_time > time_passed:
        return True
    else:
        return False

def timeCalTheSecond(current_hour, current_min, event_hour, event_min, until_time):
    '''timeCalTheSecond(current_hour, current_min, event_hour, event_min, until_time): Documentation
    Another timeCalculator function. This one calculates the time left until a certain time:
    All variables are required, all int. until_time is given in minutes.
    current_time is obvious, event_time is when the last thing happened, until_time is the time to wait'''
    try:
        current_hour = int(current_hour)
        current_min = int(current_min)
        event_hour = int(event_hour)
        event_min = int(event_min)
        until_time = int(until_time)
    except ValueError:
        return False
    current_time = 60 * current_hour + current_min
    event_time = 60 * event_hour + event_min
    next_time = event_time + until_time
    if until_time < current_time:
        until_time += 1440
    time_left = next_time - current_time
    return time_left

### Main
cmdargs = argv
if len(cmdargs) > 1:
    if cmdargs[1] in ('debug', 'devel', 'test', 'testmode', 'dbm'):
        testmode = True

print(10*' ' + " >>>>> RPI Server Status Monitor <<<<< " + 10*' ' + '\n')
print(10*' ' + "   >>> statmon.py V{0}, JTC 2019 <<<   ".format(__version__) + 10*' ')
if testmode:
    print("Developer mode initialised")
print("Initialising Terminal User Interface...")

## Main program loop
try:
    curses.wrapper(main)
except Exception as e:
    ## Wrapper should normally do this itself, but just in case
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    print(">>> Fatal error, restoring terminal")
    print(">>> The following exception was caught:")
    raise ## Re-raise the exception after the terminal has been restored.

### End Main
