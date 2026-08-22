/*
 *	linoleum_linux32 Linoleum Run-Time Module for linux 32-bit systems
 *	Copyright (C) 2004-2006 Peterpaul Klein Haneveld
 *
 *	This program is free software ;  you can redistribute it and/or
 *	modify it under the terms of the GNU General Public License
 *	as published by the Free Software Foundation ;  either version 2
 *	of the License, or (at your option) any later version.
 *
 *	This program is distributed in the hope that it will be useful,
 *	but WITHOUT ANY WARRANTY;  without even the implied warranty of
 *	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *	GNU General Public License for more details.
 *
 *	You should have received a copy of the GNU General Public License
 *	along with this program	;  if not, write to the Free Software
 *	Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

#include <stdio.h>
#include <unistd.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include "lino_globalK.h"
#include "rtm.h"
#include "lino_file.h"

unit *globalK_name;
unit globalK_filename[32768];
static char globalK_legacy_filename[32768];

/**
 * Converts a character to a valid globalK name character.
 * @param u Character to convert
 * @return '_' if u isn't alphanumeric, u otherwise
 */
static unit globalK_name_chr(unit u)
{
	if (u && (u > UCHAR_MAX || !isalnum((unsigned char) u)))
		return '_';
	return u;
}

/** copies a global k name to another location, and checks
 * and converts the name to a valid global K name
 * @param to target buffer to hold global K name
 * @param from source buffer
 * @return a pointer to the target buffer
 */
unit *lino_globalK_name_copy(unit * to, const unit * from)
{
	int i = 0;

	while (i < 24 && (to[i] = globalK_name_chr(from[i])))
		i++;

	if (i == 24)
		to[24] = '\0';

	return to;
}

static bool globalK_directory(const char *path)
{
	struct stat status;

	if (mkdir(path, 0700) == 0)
		return true;
	if (errno != EEXIST || stat(path, &status) != 0)
		return false;
	return S_ISDIR(status.st_mode);
}

static bool globalK_prepare_filename(void)
{
	const char *home = getenv("HOME");
	char path[32768];
	char name[25];
	int length;

	if (home == NULL || home[0] != '/')
		return false;
	length = snprintf(path, sizeof path, "%s/Library", home);
	if (length < 0 || (size_t) length >= sizeof path ||
	    !globalK_directory(path))
		return false;
	length = snprintf(path, sizeof path, "%s/Library/Application Support",
	    home);
	if (length < 0 || (size_t) length >= sizeof path ||
	    !globalK_directory(path))
		return false;
	length = snprintf(path, sizeof path,
	    "%s/Library/Application Support/Linoleum", home);
	if (length < 0 || (size_t) length >= sizeof path ||
	    !globalK_directory(path))
		return false;
	length = snprintf(path, sizeof path,
	    "%s/Library/Application Support/Linoleum/GlobalK", home);
	if (length < 0 || (size_t) length >= sizeof path ||
	    !globalK_directory(path))
		return false;
	if ((size_t) length + 2 > sizeof path ||
	    (size_t) length + 26 >=
	    sizeof globalK_filename / sizeof globalK_filename[0])
		return false;
	path[length++] = '/';
	path[length] = '\0';

	btrsstring(globalK_filename, path);
	globalK_name = &globalK_filename[ustrlen(globalK_filename)];
	lino_globalK_name_copy(globalK_name,
	    &pWorkspace[pUIWorkspace[mm_GlobalKName]]);
	if (globalK_name[0] == 0)
		return false;
	lino_file_realpath(globalK_filename);
	utrsstring(name, globalK_name);
	length = snprintf(globalK_legacy_filename,
	    sizeof globalK_legacy_filename, "%s/linoleum/.k/%s", home, name);
	if (length < 0 || (size_t) length >= sizeof globalK_legacy_filename)
		return false;
	return true;
}

static bool globalK_write_atomic(const char *destination, const unit *data)
{
	char temporary[32768];
	FILE *kfile;
	int descriptor;
	int length;
	bool result;

	length = snprintf(temporary, sizeof temporary, "%s.tmp.XXXXXX",
	    destination);
	if (length < 0 || (size_t) length >= sizeof temporary)
		return false;
	descriptor = mkstemp(temporary);
	if (descriptor < 0)
		return false;
	kfile = fdopen(descriptor, "wb");
	if (kfile == NULL) {
		close(descriptor);
		unlink(temporary);
		return false;
	}
	result = fwrite(data, sizeof(unit), 255, kfile) == 255;
	if (result && fflush(kfile) != 0)
		result = false;
	if (result && fsync(descriptor) != 0)
		result = false;
	if (fclose(kfile) != 0)
		result = false;
	if (result && rename(temporary, destination) == 0)
		return true;
	unlink(temporary);
	return false;
}

static FILE *globalK_open_read(void)
{
	struct stat status;
	bool new_absent;
	FILE *kfile;

	new_absent = lstat(dmsfilename, &status) != 0 && errno == ENOENT;
	kfile = fopen(dmsfilename, "rb");
	if (kfile == NULL && new_absent)
		kfile = fopen(globalK_legacy_filename, "rb");
	return kfile;
}

/**
 * handles all Global K commands.
 * @return 1 when errors, 0 otherwise
 */
bool krnlGlobalKCommand(GlobalKCommand command)
{
	FILE *kfile;
	unit read_data[255];
	bool result = true;
	size_t globalK_units;

	if (command != IDLE && !globalK_prepare_filename())
		return false;

	switch (command) {
	case IDLE:
		break;
	case KREAD:
		kfile = globalK_open_read();
		if (!kfile) {
			result = false;
			break;
		}
		globalK_units = fread(read_data, sizeof(unit), 255, kfile);
		if (globalK_units != 255)
			result = false;
		if (fclose(kfile) != 0)
			result = false;
		if (result)
			memcpy(&pWorkspace[pUIWorkspace[mm_GlobalKData]], read_data,
			    sizeof read_data);
		break;
	case KWRITE:
		result = globalK_write_atomic(dmsfilename,
		    &pWorkspace[pUIWorkspace[mm_GlobalKData]]);
		break;
	case KDESTROY:
		{
			bool removed = false;

			if (unlink(dmsfilename) == 0)
				removed = true;
			else if (errno != ENOENT)
				result = false;
			if (unlink(globalK_legacy_filename) == 0)
				removed = true;
			else if (errno != ENOENT)
				result = false;
			if (!removed)
				result = false;
		}
		break;
	default:
		result = false;
		break;
	}

	pUIWorkspace[mm_GlobalKCommand] = IDLE;
	return result;
}
