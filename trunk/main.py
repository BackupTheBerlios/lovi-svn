#!/usr/bin/env python

"""
Simple log file viewer.
"""

"""
Copyright (c) 2005 by Akos Polster

Terms and Conditions

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Except as contained in this notice, the name of the copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in this Software without prior written authorization from the
copyright holder.
"""

import datetime
import os
import sys
from qt import QButtonGroup, QFont, QFrame, QGridLayout, QLabel, QLineEdit, \
    QPopupMenu, QRadioButton, QSize, QStringList, Qt, QTabWidget, QTextEdit, \
    QTimer, QVBoxLayout, QVButtonGroup, QWhatsThis, QWidget, SIGNAL
from kdecore import i18n, KApplication, KAboutData, KCmdLineArgs, \
    KConfigSkeleton, KIcon, KIconLoader
from kdeui import KConfigDialog, KDialogBase, KFontChooser, KMainWindow, \
    KMessageBox, KStdAction
from kfile import KFileDialog

def makeCaption(title):
    """Create a standard window caption"""
    return KApplication.kApplication().makeStdCaption(i18n(title))
    
class Tail:

    """File monitor. Based on code contributed to Python Cookbook 
    by Ed Pascoe (2003)."""

    LINES_BACK = 400

    def __init__(self, fileName):
        self.fileName = fileName
        self.fd = open(fileName, "r")
        self.started = False
        self.changed = False
        
    def start(self):
        
        """Start monitoring; return the last 400 or so lines of the file."""
    
        avgCharsPerLine = 75

        while 1:
            try:
                self.fd.seek(-1 * avgCharsPerLine * Tail.LINES_BACK, 2)
            except IOError:
                self.fd.seek(0)
    
            if self.fd.tell() == 0:
                atStart = 1
            else:
                atStart = 0
    
            lines = self.fd.read().split("\n")
            if (len(lines) > (Tail.LINES_BACK + 1)) or atStart:
                break
    
            avgCharsPerLine = avgCharsPerLine * 1.3
            
        if len(lines) > Tail.LINES_BACK:
            start = len(lines) - Tail.LINES_BACK - 1
        else:
            start = 0
    
        return lines[start:len(lines) - 1]
        
    def follow(self):
        
        """Monitor file for changes: Return text appended to the file since 
        last call."""
        
        ret = []
        
        if not self.started:
            ret = self.start()
            self.started = True
        
        while 1:
            where = self.fd.tell()
            line = self.fd.readline()
            if not line:
                fdResults = os.fstat(self.fd.fileno())
                try:
                    stResults = os.stat(self.fileName)
                except OSError:
                    stResults = fdResults
                if stResults[1] == fdResults[1]:
                    self.fd.seek(where)
                else:
                    # Inode of the monitored file has changed
                    self.fd = open(self.fileName, "r")
                break
            else:
                self.changed = True
                ret.append(line.strip("\r\n"))
                
        return ret
        
    def getFileName(self):
        return self.fileName
        
    def isChanged(self):
        changed = self.changed
        self.changed = False
        return changed

class Monitor(QWidget):

    """File monitor widget."""

    MAX_LOG_LINES = 5000
    
    def __init__(self, parent, tailer, fltr = None):
        QWidget.__init__(self, parent, "")
        self.tailer = tailer
        self.filter = fltr
        self.log = QTextEdit(self)
        layout = QGridLayout(self, 1, 1)
        layout.addWidget(self.log, 0, 0)
        self.log.setTextFormat(QTextEdit.LogText)
        self.log.setMaxLogLines(Monitor.MAX_LOG_LINES)
        self.follow()
        QWhatsThis.add(self.log, 
        str(i18n("<qt>This page is monitoring changes to <b>%s</b></qt>")) 
            % self.tailer.getFileName())
        
    def follow(self):

        """Update widget with file changes."""
        
        for line in self.tailer.follow():
            hasErrors = False
            hasWarnings = False
            if self.filter:
                loLine = line.lower()
                for err in self.filter["errors"]:
                    if loLine.find(err.lower()) != -1:
                        hasErrors = True
                        break
                if not hasErrors:
                    for warn in self.filter["warnings"]:
                        if loLine.find(warn.lower()) != -1:
                            hasWarnings = True
                            break
            line = line.replace("<", "&lt;")
            if hasErrors:
                line = '<font color="red">' + line + '</font>'
            elif hasWarnings:
                line = '<font color="blue">' + line + '</font>'
                    
            self.log.append(line)
            
    def getFileName(self):
        return self.tailer.getFileName()
        
    def isChanged(self):
        return self.tailer.isChanged()
        
    def getTextWidget(self):
        """Return the text widget containing the log file changes."""
        return self.log

class BellButton(QLabel):
    """A label with a bell icon."""
    def __init__(self, *args):
        apply(QLabel.__init__, (self,) + args)
        try:
            self.setPixmap(KIconLoader().loadIcon("idea", KIcon.Small, 11))
        except:
            # Allow missing icon
            pass

class MainWin(KMainWindow):

    """Main window"""

    SB_TEXT = 1
    SB_TIMEOUT = 10000
    MON_TIMEOUT = 3000
    CHANGE_TIMEOUT = 3001

    def __init__(self, *args):
        apply(KMainWindow.__init__, (self,) + args)
        self.lastDir = "/var/log"
        self.monitors = []
        self.filter = {
            "errors": ["error", "fail", "badness"], 
            "warnings": ["warning", "cannot", "can't", "unable"]
        }
        self.currentPage = None
        self.tab = QTabWidget(self)
        self.settingsDlg = SettingsDlg(self)
        self.setCentralWidget(self.tab)
        self.connect(self.tab, SIGNAL("currentChanged(QWidget *)"), 
            self.onPageChange)
        self.setGeometry(0, 0, 600, 400)
        self.setCaption(makeCaption("(none)"))

        # Timers
        self.timer = QTimer(self)
        self.timer.start(MainWin.MON_TIMEOUT)
        self.statusTimer = QTimer(self)
        self.connect(self.statusTimer, SIGNAL("timeout()"), 
            self.onStatusTimeout)
        self.changeTimer = QTimer(self)
        self.changeTimer.start(MainWin.CHANGE_TIMEOUT)
        self.connect(self.changeTimer, SIGNAL("timeout()"),
            self.onChangeTimeout)

        # Initialize actions
        actions = self.actionCollection()
        self.openAction = KStdAction.open(self.onOpen, actions)
        self.closeAction = KStdAction.close(self.onClose, actions)
        self.closeAction.setEnabled(False)
        self.quitAction = KStdAction.quit(self.onQuit, actions)
        self.copyAction = KStdAction.copy(self.onCopy, actions)
        self.copyAction.setEnabled(False)
        self.clearAction = KStdAction.clear(self.onClear, actions)
        self.clearAction.setEnabled(False)
        self.selectAllAction = KStdAction.selectAll(self.onSelectAll, actions)
        self.selectAllAction.setEnabled(False)
        self.addBookmarkAction = \
            KStdAction.addBookmark(self.onAddBookmark, actions)
        self.addBookmarkAction.setEnabled(False)
        self.settingsAction = KStdAction.preferences(self.onSettings, actions)
        
        # Initialize menus
        
        fileMenu = QPopupMenu(self)
        self.openAction.plug(fileMenu)
        self.closeAction.plug(fileMenu)
        fileMenu.insertSeparator()
        self.quitAction.plug(fileMenu)
        self.menuBar().insertItem(i18n("&File"), fileMenu)
        
        editMenu = QPopupMenu(self)
        self.copyAction.plug(editMenu)
        self.clearAction.plug(editMenu)
        editMenu.insertSeparator()
        self.selectAllAction.plug(editMenu)
        self.addBookmarkAction.plug(editMenu)
        self.menuBar().insertItem(i18n("&Edit"), editMenu)
        
        settingsMenu = QPopupMenu(self)
        self.settingsAction.plug(settingsMenu)
        self.menuBar().insertItem(i18n("&Settings"), settingsMenu)
        
        helpMenu = self.helpMenu("")
        self.menuBar().insertItem(i18n("&Help"), helpMenu)
        
        # Initialize status bar
        self.sb = self.statusBar()
        self.bell = BellButton(None)
        self.displayStatus(False, "")
        
    def displayStatus(self, changed, msg):
        """Display a message in the status bar."""
        self.statusTimer.stop()
        self.sb.removeWidget(self.bell)
        self.sb.removeItem(MainWin.SB_TEXT)
        if changed:
            self.sb.addWidget(self.bell, 1, False)
        self.sb.insertItem(msg, MainWin.SB_TEXT, 1000, True)
        self.sb.setItemAlignment(MainWin.SB_TEXT, 
                                 Qt.AlignLeft|Qt.AlignVCenter)
        self.statusTimer.start(MainWin.SB_TIMEOUT, True)
       
    def onOpen(self, id = -1):
        """Open file for monitoring."""
        fileName = KFileDialog.getOpenFileName(self.lastDir, "*", self, 
            str(i18n("Open Log File")))
        if not fileName.isEmpty():
            fileName = str(fileName)
            self.lastDir = os.path.dirname(fileName)
            self.monitor(fileName)
    
    def onClose(self, id = -1):
        """Close a monitored file."""
        self.monitors.remove(self.currentPage)
        self.currentPage.close()
        self.tab.removePage(self.currentPage)
        self.displayStatus(False, "")
        self.updateConfig()
        if len(self.monitors) == 0:
            # Update interface when the last page is deleted
            self.setCaption(makeCaption("(none)"))
            self.closeAction.setEnabled(False)
            self.copyAction.setEnabled(False)
            self.selectAllAction.setEnabled(False)
            self.clearAction.setEnabled(False)
            self.addBookmarkAction.setEnabled(False)

    def onQuit(self, id = -1):
        """Quit application."""
        self.close()
        
    def onCopy(self, id = -1):
        """Copy text to clipboard."""
        self.currentPage.getTextWidget().copy()
        
    def onClear(self, id = -1):
        """Clear text window."""
        self.currentPage.getTextWidget().setText("")
        
    def onSelectAll(self, id = -1):
        """Select all text."""
        self.currentPage.getTextWidget().selectAll(True)
        
    def onAddBookmark(self, id = -1):
        """Add a bookmark to the log."""
        bookmark = "<font color=\"blue\">"
        bookmark += datetime.datetime.now().strftime("%b %d %H:%M:%S ")
        bookmark += "-------------------------------------------------</font>"
        self.currentPage.getTextWidget().append(bookmark)
    
    def onSettings(self, id = -1):
        """Display settings dialog"""
        if KConfigDialog.showDialog("settings"):
            return
        self.settingsDlg.show()
        
    def onPageChange(self, page):
        """Update widget when the top level tab changes."""
        self.currentPage = page
        self.setCaption(makeCaption(os.path.basename(page.getFileName())))
        self.copyAction.setEnabled(page.getTextWidget().hasSelectedText())
                        
    def onStatusTimeout(self):
        """Clear status bar on timeout."""
        self.displayStatus(False, "")
        
    def onChangeTimeout(self):
        """Look for changes in monitored files. """
        changeList = []
        for m in self.monitors:
            if m.isChanged():
                changeList.append(os.path.basename(m.getFileName()))
        if len(changeList):
            msg = changeList[0]
            for f in changeList[1:]:
                msg += ", %s" % f
            msg = str(i18n("Change to %s")) % msg
            self.displayStatus(True, msg)
            
    def onCopyAvailable(self, available):
        """Update Copy menu item when there is a selection available."""
        self.copyAction.setEnabled(available)

    def monitor(self, fileName):
        """Start monitoring a file."""
        try:
            tailer = Tail(fileName)
        except:
            KMessageBox.error(self, 
                str(i18n("Cannot open file for monitoring:\n%s")) % 
                    fileName, makeCaption("Error"))
            return
        mon = Monitor(self.tab, tailer, self.filter)
        base = os.path.basename(fileName)
        self.monitors.append(mon)
        self.tab.addTab(mon, base)
        self.tab.showPage(mon)
        self.currentPage = mon
        self.setCaption(makeCaption(base))
        self.displayStatus(False, str(i18n("Monitoring %s")) % fileName)
        self.connect(self.timer, SIGNAL("timeout()"), mon.follow)
        self.updateConfig()
        self.connect(mon.getTextWidget(), SIGNAL("copyAvailable(bool)"), 
            self.onCopyAvailable)
        self.closeAction.setEnabled(True)
        self.copyAction.setEnabled(False)
        self.clearAction.setEnabled(True)
        self.selectAllAction.setEnabled(True)
        self.addBookmarkAction.setEnabled(True)
        
    def updateConfig(self):
        """Update the list of monitored files in the configuration file."""
        files = []
        for mon in self.monitors:
            files.append(mon.getFileName())
        cfg = KApplication.kApplication().config()
        cfg.setGroup("Monitor")
        cfg.writeEntry("files", files)
        
class LoviConfig:

    """Configuration singleton"""

    class LoviConfig_(KConfigSkeleton):
        """Configuration information""" 
        def __init__(self, *args):
            KConfigSkeleton.__init__(self, *args)
            self.setCurrentGroup("Font")
            self.fontDefault = self.addItemBool("fontDefault", True)
            self.fontFixed = self.addItemBool("fontFixed", False)
            self.fontCustom = self.addItemBool("fontCustom", False)
            self.readConfig()

    instance_ = None

    def __init__(self):
        if LoviConfig.instance_ is None:
            LoviConfig.instance_ = self.LoviConfig_()
            
    def getInstance(self):
        return LoviConfig.instance_

class SettingsDlg(KConfigDialog):
    
    """Settings dialog"""
    
    def __init__(self, parent):
        
        KConfigDialog.__init__(self, parent, "settings",
            LoviConfig().getInstance(), KDialogBase.IconList, 
            KDialogBase.Ok | KDialogBase.Apply | KDialogBase.Cancel)
            
        font = QWidget(self, "Font")
        box = QVBoxLayout(font, 3, 3)
        fontGrp = QVButtonGroup("", font)
        fontGrp.setFrameStyle(QFrame.NoFrame)
        kcfg_fontDefault = \
            QRadioButton(i18n("Default font"), fontGrp, "kcfg_fontDefault")
        kcfg_fontFixed = \
            QRadioButton(i18n("Default fixed font"), fontGrp, "kcfg_fontFixed")
        kcfg_fontCustom = \
            QRadioButton(i18n("Custom:"), fontGrp, "kcfg_fontCustom")
        fontGrp.setExclusive(True)
        box.addWidget(fontGrp)
        fontChooser = KFontChooser(font, "", False, QStringList(), False)
        box.addWidget(fontChooser)
        
        filters = QWidget(None, "filters")

        actions = QWidget(None, "actions")

        self.addPage(font, i18n("Font"), "fonts")
        self.addPage(filters, i18n("Filters"), "2downarrow")
        self.addPage(actions, i18n("Alarms"), "kalarm")

def main():

    """Main program."""

    description = str(i18n("Simple log file viewer"))
    version = "0.2"
    about = KAboutData("lovi", "lovi", version, description,
        KAboutData.License_GPL, "(C) 2005 Akos Polster")
    about.addAuthor("Akos Polster", "", "akos@pipacs.com")
    KCmdLineArgs.init(sys.argv, about)
    KCmdLineArgs.addCmdLineOptions([("+files", "Files to open")])
    app = KApplication()
    mainWindow = MainWin(None, "lovi#")
    app.setMainWidget(mainWindow)
    
    # Get list of monitored files from the command line or from the cfg file
    args = KCmdLineArgs.parsedArgs()
    if args.count() > 0:
        for i in range(0, args.count()):
            mainWindow.monitor(args.arg(i))
    else:
        cfg = app.config()
        cfg.setGroup("Monitor")
        files = cfg.readListEntry("files")
        for f in files:
            mainWindow.monitor(str(f))
        
    mainWindow.show()
    app.exec_loop()

if __name__ == "__main__":
    main()
