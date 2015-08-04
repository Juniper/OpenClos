import re
import cli_parser
from cli_handle_impl import CLIImplementor

cmds=["update_password_for-pod_<podid>", 
"update_password_for-pod_<podid>_for-device_<deviceid>", 
"update_pods_for-pod_<podid>", 
"show_pods_detail_all"]

needle= "update password for-pod 
f72e8af5-94c8-4ccc-9b3a-be002ed8bab7 for-device 2"


#Need to be altered once integrated
cli_util=cli_parser.CLIUtil()
cmd_graph_helper = cli_util.return_cmd_graph()
macro_dict={}

def get_match (needle, cmds):
	if len(needle)==0 or re.search("[a-z|A-Z|0-9]", needle)==None:
	    return cli_util.get_all_cmds()
	if needle[-1]==" ":
	    needle=needle[0:-1]
	needle = cli_util.normalize_command(needle)
	ret_list = []
	for haystack_orig in cmds:
	    #ret_list = []
		
	    #Need to be altered once integrated
	    cmd_helper = cmd_graph_helper[haystack_orig]	
		
	    if cmd_helper.cmd_macro!="":
		cmd_macro_list = cli_util.get_macro_list(CLIImplementor(),cmd_helper.cmd_macro)
		macro_dict[cmd_helper.cmd_macroname]=cmd_macro_list
	    haystack = haystack_orig.replace("<","(?P<")
	    haystack = haystack.replace(">", ">.*)")
	    print "needle: " + needle
	    print "haystack: " + haystack
	    match_macros = re.search(haystack,needle)
	    if len(haystack_orig)<len(needle):	
		match_object = re.match(haystack_orig,needle)
	    else:
		match_object = re.match(needle,haystack_orig)
		
	    # Complete partial command case
	    if match_object!=None:
		print "first case"
		balance_haystack = haystack_orig[match_object.end():]
		#if haystack_orig.count("<") < 2:
		if cmd_helper.cmd_macroname in haystack_orig.partition(">")[0]:
		    if balance_haystack[1]=="<" and cmd_helper.cmd_macro!="":
			cli_util.include_macro(macro_dict[cmd_helper.cmd_macroname],ret_list)
		else:
		    haystack_orig=haystack_orig.replace(" ","_")
		    cli_util.complete_command(needle,haystack_orig,match_object.end(), cmd_helper, ret_list)
		
	    # Compare and complete macros case
	    elif match_macros!=None:
		#print "second case"
		for macro_name in macro_dict.keys():
		    try:
			macro_needle = match_macros.group(macro_name)
			if "_" in macro_needle:
			    continue
			flag=0
			for each_macro in macro_dict[macro_name]:
			    if macro_needle in each_macro:
				cli_util.match_macro(macro_dict[macro_name],macro_needle,ret_list)
				flag=1
				break
						
			if flag==0:
			    print "Invalid macro. Possible options:"
			    cli_util.include_macro(macro_dict[macro_name],ret_list)
						
					
		    except IndexError:
			break

	    # Find point of match and return remaining command case
	    else:
		needle_temp = needle
		haystack_temp = haystack_orig
		while True:
		    index_of_diff = 0
		    for char_a, char_b in zip(list(haystack_temp), list(needle_temp)):
			if char_a!=char_b:
			    break
			index_of_diff=index_of_diff+1
		
		    if index_of_diff!=0:
			macro_needle = needle_temp[index_of_diff:]
			macro_needle = macro_needle.split("_",1)[-1]
			balance_haystack = haystack_temp[index_of_diff:]
				
			if balance_haystack[0]=="_":
			    balance_haystack=balance_haystack[1:]
					
			if balance_haystack[0]=="<":
			    balance_haystack=balance_haystack.split("_",1)[-1]
			    match_object = re.match(macro_needle, balance_haystack)
			    # When needle ends with a macro
			    if match_object==None or macro_needle=="":
				#print "Incorrect command. Possible options:"
				if balance_haystack[0]=="<" and cmd_helper.cmd_macro!="":
				    cli_util.include_macro(macro_dict[cmd_helper.cmd_macroname],ret_list)
				else:
				    end_pos = haystack_orig.find(balance_haystack)
				    cli_util.complete_command(haystack_orig[:end_pos],haystack_orig,end_pos, cmd_helper, ret_list)
				break

			    # When needle extends beyond current macro
			    elif match_object!=None:
				haystack_temp = balance_haystack
				needle_temp = macro_needle
			else:
			    break
		    else:
			break	
	print ret_list
		

get_match(needle,cmds)
