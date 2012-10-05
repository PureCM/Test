import sublime
import sublime_plugin

import os
import stat
import subprocess
import tempfile
import threading

# Plugin Settings are located in 'Purecm.sublime-settings' make a copy in the User folder to keep changes

def ConstructCommand(in_command):
	command = ''

	if(sublime.platform() == "osx"):
		command = 'source ~/.bash_profile && '
	command += in_command
	return command

def IsWorkspaceMonitorRunning():
	return subprocess.call('pcm info -w', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True) == 0

def PurecmCommandOnFile(in_command, in_folder, in_filename):
	commandParam = 'pcm ' + in_command

	if (in_filename.__len__() > 0):
		commandParam += (' "' + in_filename + '"')
	command = ConstructCommand(commandParam)
	print "PureCM: " + command
	p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=in_folder, shell=True)
	result, err = p.communicate()

	if(not err):
		return 1, result.strip()
	else:
		return 0, err.strip()   

def WarnUser(message):
	Purecm_settings = sublime.load_settings('Purecm.sublime-settings')
	if(Purecm_settings.get('purecm_warnings_enabled')):
		if(Purecm_settings.get('Purecm_log_warnings_to_status')):
			sublime.status_message("Purecm [warning]: " + message)
		else:
			print("Purecm [warning]: " + message);

def LogResults(success, message):
	if(success >= 0):
		print "Purecm: " + message
	else:
		WarnUser(message);

def IsFileWritable(in_filename):
	if(not in_filename):
		return 0

	# if it doesn't exist, it's "writable"
	if(not os.path.isfile(in_filename)):
		return 1

	filestats = os.stat(in_filename)[0];
	if(filestats & stat.S_IWRITE):
		return 1
	return 0

def Checkout(in_filename):
	if(IsFileWritable(in_filename)):
		return -1, "File is already writable."

	folder_name, filename = os.path.split(in_filename)

	return PurecmCommandOnFile("checkout", folder_name, in_filename);

class BackgroundCheckout(threading.Thread):
	def __init__(self,fname):
		self.fname = fname
		threading.Thread.__init__(self)
		
	def run(self):
		print "BackgroundCheckout.run (Thread) fname=" + self.fname
		success, message = Checkout(self.fname)
		LogResults(success, message);
		self.result = True
		return

class PurecmAutoCheckout(sublime_plugin.EventListener):  
	def on_modified(self, view):
		if(not view.file_name()):
			return

		if(IsFileWritable(view.file_name())):
			print "PurecmAutoCheckout:on_modified not checking out because already writeable: " + view.file_name()
			return

		Purecm_settings = sublime.load_settings('Purecm.sublime-settings')

		# check if this part of the plugin is enabled
		if(not Purecm_settings.get('purecm_auto_checkout') or not Purecm_settings.get('purecm_auto_checkout_on_modified')):
			return
			  
		if(view.is_dirty()):
			thread = BackgroundCheckout(view.file_name())
			thread.start()

	def on_pre_save(self, view):
		Purecm_settings = sublime.load_settings('Purecm.sublime-settings')

		# check if this part of the plugin is enabled
		if(not Purecm_settings.get('purecm_auto_checkout') or not Purecm_settings.get('purecm_auto_checkout_on_save')):
			return
			  
		if(view.is_dirty()):
			success, message = Checkout(view.file_name())
			LogResults(success, message);

class PurecmCheckoutCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		print "PurecmCheckoutCommand.run"
		if(self.view.file_name()):
			success, message = Checkout(self.view.file_name())
			LogResults(success, message)
		else:
			WarnUser("View does not contain a file")

def Add(in_folder, in_filename):
	return PurecmCommandOnFile("add", in_folder, in_filename);

class PurecmAutoAdd(sublime_plugin.EventListener):
	def on_pre_save(self, view):
		Purecm_settings = sublime.load_settings('Purecm.sublime-settings')

		# check if this part of the plugin is enabled
		if(not Purecm_settings.get('Purecm_auto_add')):
			WarnUser("Auto Add disabled")
			return

		folder_name, filename = os.path.split(view.file_name())

	def on_post_save(self, view):
		folder_name, filename = os.path.split(view.file_name())
		success, message = Add(folder_name, filename)
		LogResults(success, message)

class PurecmAddCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		if(self.view.file_name()):
			folder_name, filename = os.path.split(self.view.file_name())

			success, message = Add(folder_name, filename)

			LogResults(success, message)
		else:
			WarnUser("View does not contain a file")

def Delete(in_folder, in_filename):
	success, message = PurecmCommandOnFile("delete", in_folder, in_filename)
	if(success):
		# test if the file is deleted
		if(os.path.isfile(os.path.join(in_folder, in_filename))):
			success = 0

	return success, message

class PurecmDeleteCommand(sublime_plugin.WindowCommand):
	def run(self):
		if(self.window.active_view().file_name()):
			folder_name, filename = os.path.split(self.window.active_view().file_name())
			success, message = Delete(folder_name, filename)
			if(success): # the file was properly deleted on Purecm, ask Sublime Text to close the view
				self.window.run_command('close');
			LogResults(success, message)
		else:
			WarnUser("View does not contain a file")

def Revert(in_folder, in_filename):
	return PurecmCommandOnFile("revert", in_folder, in_filename);

class PurecmRevertCommand(sublime_plugin.TextCommand):
	def run_(self, args): # revert cannot be called when an Edit object exists, manually handle the run routine
		if(self.view.file_name()):
			folder_name, filename = os.path.split(self.view.file_name())
			success, message = Revert(folder_name, filename)
			if(success): # the file was properly reverted, ask Sublime Text to refresh the view
				self.view.run_command('revert');
			LogResults(success, message)
		else:
			WarnUser("View does not contain a file")

def CreateOutputWindow(text):
	v = sublime.active_window().get_output_panel('PureCM')

	# Write this text to the output panel and display it
	edit = v.begin_edit()
	v.insert(edit, v.size(), text + '\n')
	v.end_edit(edit)
	v.show(v.size())

	sublime.active_window().run_command("show_panel", {"panel": "output.PureCM"})

def Diff(in_folder, in_filename, guimode):
	if (guimode):
		return PurecmCommandOnFile("diff -G", in_folder, in_filename);
	else:
		return PurecmCommandOnFile("diff -U", in_folder, in_filename);

class PurecmDiffCommand(sublime_plugin.TextCommand):
	def run(self, edit): 
		if(self.view.file_name()):
			folder_name, filename = os.path.split(self.view.file_name())

			if(IsWorkspaceMonitorRunning()):
				success, message = Diff(folder_name, filename, True)
				LogResults(success, message)
			else:
				success, message = Diff(folder_name, filename, False)

				if ( message.__len__() == 0 ):
					message = "<No Differences Found>"
				CreateOutputWindow(message)
		else:
			WarnUser("View does not contain a file")

def History(in_folder, in_filename, guimode):
	if (guimode):
		return PurecmCommandOnFile("history -G", in_folder, in_filename);
	else:
		return PurecmCommandOnFile("history", in_folder, in_filename);

class PurecmHistoryCommand(sublime_plugin.TextCommand):
	def run(self, edit): 
		if(self.view.file_name()):
			folder_name, filename = os.path.split(self.view.file_name())

			if(IsWorkspaceMonitorRunning()):
				success, message = History(folder_name, filename, True)
				LogResults(success, message)
			else:
				success, message = History(folder_name, filename, False)
				CreateOutputWindow(message)
		else:
			WarnUser("View does not contain a file")

def Submit(in_folder, guimode):
	if ( guimode ):
		return PurecmCommandOnFile("submit -G", in_folder, '')
	else:
		return PurecmCommandOnFile("submit", in_folder, '')

class PurecmSubmitCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		if(self.view.file_name()):
			folder_name, filename = os.path.split(self.view.file_name())

			if(IsWorkspaceMonitorRunning()):		
				success, message = Submit(folder_name, True)
				LogResults(success, message)
			else:
				success, message = Submit(folder_name, False)

				CreateOutputWindow(message)
		else:
			WarnUser("View does not contain a file")

def Update(in_folder, guimode):
	if ( guimode ):
		return PurecmCommandOnFile("update -G", in_folder, '')
	else:
		return PurecmCommandOnFile("update", in_folder, '')

class PurecmUpdateCommand(sublime_plugin.TextCommand):
	def run(self, edit): 
		if(self.view.file_name()):
			folder_name, filename = os.path.split(self.view.file_name())

			if(IsWorkspaceMonitorRunning()):
				success, message = Update(folder_name, True)
				LogResults(success, message)
			else:
				success, message = Update(folder_name, False)

				CreateOutputWindow(message)
		else:
			WarnUser("View does not contain a file")		

def CheckConsistency(in_folder, guimode):
	if ( guimode ):
		return PurecmCommandOnFile("consistency --guimode", in_folder, '')
	else:
		return PurecmCommandOnFile("consistency", in_folder, '')

class PurecmConsistencyCommand(sublime_plugin.TextCommand):
	def run(self, edit): 
		if(self.view.file_name()):
			folder_name, filename = os.path.split(self.view.file_name())

			if(IsWorkspaceMonitorRunning()):
				success, message = CheckConsistency(folder_name, True)
				LogResults(success, message)
			else:
				success, message = CheckConsistency(folder_name, False)

				CreateOutputWindow(message)
		else:
			WarnUser("View does not contain a file")