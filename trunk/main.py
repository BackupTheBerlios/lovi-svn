#!/usr/bin/env python

"""
Simple log file viewer.
"""

"""
Copyright (c) 2005-2006 by Akos Polster

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
from qt import QButtonGroup, QFont, QFrame, QGridLayout, QIconSet, QLabel, \
    QLineEdit, QPopupMenu, QRadioButton, QSize, QString, QStringList, Qt, \
    QTabWidget, QTextEdit, QTimer, QVBoxLayout, QVButtonGroup, QWhatsThis, \
    QWidget, SIGNAL
from kdecore import i18n, KApplication, KAboutData, KCmdLineArgs, \
    KConfigSkeleton, KGlobalSettings, KIcon, KIconLoader
from kdeui import KConfigDialog, KDialogBase, KFontChooser, KMainWindow, \
    KMessageBox, KStdAction
from kfile import KFileDialog


def makeCaption(title):
    """Create a standard window caption"""
    return KApplication.kApplication().makeStdCaption(i18n(title))
    

class Tail:

    """
    File monitor.
    
    Based on code contributed to Python Cookbook by Ed Pascoe (2003).
    """

    LINES_BACK = 700
    LINES_AT_ONCE = 700

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
        
        for cnt in range(0, Tail.LINES_AT_ONCE):
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

    MAX_LOG_LINES = 1000
    
    def __init__(self, parent, tailer):
        QWidget.__init__(self, parent, "")
        self.tailer = tailer
        self.cfg = LoviConfig().getInstance()
        self.log = QTextEdit(self)
        layout = QGridLayout(self, 1, 1)
        layout.addWidget(self.log, 0, 0)
        self.log.setTextFormat(QTextEdit.LogText)
        self.log.setMaxLogLines(Monitor.MAX_LOG_LINES)
        self.follow()
        QWhatsThis.add(self.log, 
            str(i18n("<qt>This page is monitoring changes to <b>%s</b></qt>")) 
                % self.tailer.getFileName())
        self.reconfigure()
        
    def follow(self):

        """Update widget with file changes."""
        
        for line in self.tailer.follow():
            hasErrors = False
            hasWarnings = False
            loLine = line.lower()
            for err in self.cfg.filterErrorList:
                if loLine.find(err.lower()) != -1:
                    hasErrors = True
                    break
            if not hasErrors:
                for warn in self.cfg.filterWarningList:
                    if loLine.find(warn.lower()) != -1:
                        hasWarnings = True
                        break
            line = line.replace("<", "&lt;").replace(">", "&gt;")
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
    
    def reconfigure(self):
        """Update with configuration changes."""
        if self.cfg.fontDefault[0].property().toInt():
            self.log.setFont(KGlobalSettings.generalFont())
        elif self.cfg.fontFixed[0].property().toInt():
            self.log.setFont(KGlobalSettings.fixedFont())
        else:
            self.log.setFont(self.cfg.font.property().toFont())


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
    MON_TIMEOUT = 1000
    CHANGE_TIMEOUT = 3001

    def __init__(self, *args):
        apply(KMainWindow.__init__, (self,) + args)
        
        self.lastDir = "/var/log"
        self.monitors = []
        self.currentPage = None
        self.tab = QTabWidget(self)
        self.settingsDlg = SettingsDlg(self)
        self.cfg = LoviConfig().getInstance()
        self.bellIcon = \
            QIconSet(KIconLoader().loadIcon("idea", KIcon.Small, 11))
        self.noIcon = QIconSet()
        
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
        self.saveFileList()
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
        bookmark += "--------------------------------------------------------"
        bookmark += "</font>"
        self.currentPage.getTextWidget().append(bookmark)
    
    def onSettings(self, id = -1):
        """Display settings dialog"""
        if self.settingsDlg.exec_loop():
            self.cfg.writeConfig()
            self.cfg.processConfig()
            self.reconfigure()
        
    def onPageChange(self, page):
        """Update widget when the top level tab changes."""
        self.currentPage = page
        self.setCaption(makeCaption(os.path.basename(page.getFileName())))
        self.copyAction.setEnabled(page.getTextWidget().hasSelectedText())
        # self.tab.setTabIconSet(page, self.noIcon)
                        
    def onStatusTimeout(self):
        """Clear status bar on timeout."""
        self.displayStatus(False, "")
        for m in self.monitors:
            self.tab.setTabIconSet(m, self.noIcon)
        
    def onChangeTimeout(self):
        """Look for changes in monitored files. """
        changeList = []
        for m in self.monitors:
            if m.isChanged():
                changeList.append(os.path.basename(m.getFileName()))
                self.tab.setTabIconSet(m, self.bellIcon)
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
        mon = Monitor(self.tab, tailer)
        base = os.path.basename(fileName)
        self.monitors.append(mon)
        self.tab.addTab(mon, base)
        self.tab.showPage(mon)
        self.tab.setTabToolTip(mon, fileName)
        self.currentPage = mon
        self.setCaption(makeCaption(base))
        self.displayStatus(False, str(i18n("Monitoring %s")) % fileName)
        self.connect(self.timer, SIGNAL("timeout()"), mon.follow)
        self.saveFileList()
        self.connect(mon.getTextWidget(), SIGNAL("copyAvailable(bool)"), 
            self.onCopyAvailable)
        self.closeAction.setEnabled(True)
        self.copyAction.setEnabled(False)
        self.clearAction.setEnabled(True)
        self.selectAllAction.setEnabled(True)
        self.addBookmarkAction.setEnabled(True)
        
    def saveFileList(self):
        """Update the list of monitored files in the configuration file."""
        files = []
        for mon in self.monitors:
            files.append(mon.getFileName())
        cfg = KApplication.kApplication().config()
        cfg.setGroup("Monitor")
        cfg.writeEntry("files", files)
        
    def reconfigure(self):
        """Update self with configuration changes."""
        for mon in self.monitors:
            mon.reconfigure()
        

class LoviConfig:

    """Configuration singleton."""

    class LoviConfig_(KConfigSkeleton):
        """Configuration information""" 
        
        WARNINGS = "warn, can't, cannot, unable"
        ERRORS = "error, fail, badness"
        
        def __init__(self, *args):
            KConfigSkeleton.__init__(self, *args)
            
            self.filterErrorList = []
            self.filterWarningList = []
            
            self.setCurrentGroup("Font")
            self.fontDefault = self.addItemBool("fontDefault", True)
            self.fontFixed = self.addItemBool("fontFixed", False)
            self.fontCustom = self.addItemBool("fontCustom", False)
            self.fontVal = QFont()
            self.font = self.addItemFont("font", self.fontVal, QFont())
            
            self.setCurrentGroup("Filters")
            self.filterErrorsVal = QString()
            self.filterErrors = self.addItemString("filterErrors",
                self.filterErrorsVal, LoviConfig.LoviConfig_.ERRORS)
            self.filterWarningsVal = QString()
            self.filterWarnings = self.addItemString("filterWarnings",
                self.filterWarningsVal, LoviConfig.LoviConfig_.WARNINGS)

            self.readConfig()
            self.processConfig()
            
        def processConfig(self):
            self.filterErrorList = []
            for s in str(self.filterErrorsVal).split(","):
                self.filterErrorList.append(s.strip())
            self.filterWarningList = []
            for s in str(self.filterWarningsVal).split(","):
                self.filterWarningList.append(s.strip())

    instance_ = None

    def __init__(self):
        if LoviConfig.instance_ is None:
            LoviConfig.instance_ = self.LoviConfig_()
            
    def getInstance(self):
        return LoviConfig.instance_


class SettingsDlg(KConfigDialog):
    
    """Settings dialog."""
    
    def __init__(self, parent):
    
        cfg = LoviConfig().getInstance()
        
        KConfigDialog.__init__(self, parent, "settings",
            cfg, KDialogBase.IconList, KDialogBase.Ok | KDialogBase.Cancel)
            
        fontPage = QWidget(self, "Font")

        box = QVBoxLayout(fontPage, 3, 3)
        fontGrp = QVButtonGroup("", fontPage)
        fontGrp.setFrameStyle(QFrame.NoFrame)
        self.kcfg_fontDefault = \
            QRadioButton(i18n("Default font"), fontGrp, "kcfg_fontDefault")
        self.kcfg_fontFixed = \
            QRadioButton(i18n("Default fixed font"), fontGrp, "kcfg_fontFixed")
        self.kcfg_fontCustom = \
            QRadioButton(i18n("Custom:"), fontGrp, "kcfg_fontCustom")
        fontGrp.setExclusive(True)
        box.addWidget(fontGrp)
        self.kcfg_font = \
            KFontChooser(fontPage, "kcfg_font", False, QStringList(), False)
        box.addWidget(self.kcfg_font)
        
        filtersPage = QWidget(self, "filters")
        
        box = QGridLayout(filtersPage, 3, 2, 3, 7)
        box.addWidget(QLabel(i18n("Errors:"), filtersPage), 0, 0)
        self.kcfg_filterErrors = QLineEdit(cfg.filterErrorsVal, filtersPage, 
            "kcfg_filterErrors")
        box.addWidget(self.kcfg_filterErrors, 0, 1)
        box.addWidget(QLabel(i18n("Warnings:"), filtersPage), 1, 0)
        self.kcfg_filterWarnings = QLineEdit(cfg.filterWarningsVal, 
            filtersPage, "kcfg_filterWarnings")
        box.addWidget(self.kcfg_filterWarnings, 1, 1)
        box.setRowStretch(2, 1)

        # actionsPage = QWidget(self, "actions")

        self.addPage(fontPage, i18n("Font"), "fonts")
        self.addPage(filtersPage, i18n("Filters"), "2downarrow")
        # self.addPage(actionsPage, i18n("Alarms"), "kalarm")


def main():

    """Main program."""

    description = str(i18n("Simple log file viewer"))
    version = "0.2"
    about = KAboutData("lovi", "lovi", version, description,
        KAboutData.License_GPL, "Copyright (C) 2005-2006 by Akos Polster")
    about.addAuthor("Akos Polster", "", "akos@pipacs.com")
    KCmdLineArgs.init(sys.argv, about)
    KCmdLineArgs.addCmdLineOptions([("+files", "Files to monitor")])
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
