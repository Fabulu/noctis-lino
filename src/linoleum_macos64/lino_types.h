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

#ifndef __LINO_TYPES_H
#define __LINO_TYPES_H

#include <inttypes.h>

typedef int32_t unit;

/* Cocoa imports stdbool.h before the RTM headers. Keep the historical
 * integer-sized runtime ABI instead of letting that translation unit silently
 * change every bool return value to C99 _Bool. */
#ifdef bool
#undef bool
#endif
#ifdef false
#undef false
#endif
#ifdef true
#undef true
#endif
typedef int bool;
#define false 0
#define true (!false)

#endif
