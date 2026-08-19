/* Finder-safe launcher for the Noctis IV macOS application bundle. */

#include <mach-o/dyld.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pwd.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif

static const char *const static_resources[] = {
	"globes.map",
	"offsets.map",
	"vehicle.ncc",
	"mammal.ncc",
	"birdy.ncc",
	"digimap2.bin",
	"noctis_music.pcm",
};

static const char *const mutable_seeds[] = {
	"STARMAP.BIN",
	"GUIDE.BIN",
};

static int path_printf(char *path, size_t size, const char *format,
    const char *first, const char *second)
{
	int length = snprintf(path, size, format, first, second);
	if (length < 0 || (size_t) length >= size) {
		errno = ENAMETOOLONG;
		return -1;
	}
	return 0;
}

static int require_directory(const char *path)
{
	struct stat status;

	if (mkdir(path, 0700) == 0)
		return 0;
	if (errno != EEXIST || stat(path, &status) != 0 ||
	    !S_ISDIR(status.st_mode))
		return -1;
	return 0;
}

static int make_directories(const char *path)
{
	char partial[PATH_MAX];
	char *cursor;

	if (path[0] != '/' || strlen(path) >= sizeof partial) {
		errno = EINVAL;
		return -1;
	}
	strcpy(partial, path);
	for (cursor = partial + 1; *cursor != '\0'; cursor++) {
		if (*cursor != '/')
			continue;
		*cursor = '\0';
		if (require_directory(partial) != 0)
			return -1;
		*cursor = '/';
	}
	return require_directory(partial);
}

static int copy_file_atomic(const char *source, const char *destination)
{
	char temporary[PATH_MAX] = { 0 };
	unsigned char buffer[65536];
	struct stat status;
	int input = -1;
	int output = -1;
	int result = -1;
	int saved_error;

	input = open(source, O_RDONLY | O_CLOEXEC);
	if (input < 0 || fstat(input, &status) != 0 ||
	    !S_ISREG(status.st_mode))
		goto done;
	if (strlen(destination) + sizeof ".tmp.XXXXXX" > sizeof temporary) {
		errno = ENAMETOOLONG;
		goto done;
	}
	strcpy(temporary, destination);
	strcat(temporary, ".tmp.XXXXXX");
	output = mkstemp(temporary);
	if (output < 0)
		goto done;
	if (fchmod(output, 0644) != 0)
		goto done;
	for (;;) {
		ssize_t received = read(input, buffer, sizeof buffer);
		ssize_t written = 0;
		if (received == 0)
			break;
		if (received < 0) {
			if (errno == EINTR)
				continue;
			goto done;
		}
		while (written < received) {
			ssize_t count = write(output, buffer + written,
			    (size_t) (received - written));
			if (count < 0) {
				if (errno == EINTR)
					continue;
				goto done;
			}
			if (count == 0) {
				errno = EIO;
				goto done;
			}
			written += count;
		}
	}
	if (fsync(output) != 0)
		goto done;
	if (close(output) != 0) {
		output = -1;
		goto done;
	}
	output = -1;
	if (rename(temporary, destination) != 0)
		goto done;
	result = 0;

done:
	saved_error = errno;
	if (input >= 0)
		close(input);
	if (output >= 0)
		close(output);
	if (result != 0 && temporary[0] != '\0')
		unlink(temporary);
	if (result != 0)
		errno = saved_error;
	return result;
}

static ssize_t read_retry(int descriptor, void *buffer, size_t size)
{
	ssize_t result;
	do {
		result = read(descriptor, buffer, size);
	} while (result < 0 && errno == EINTR);
	return result;
}

static int files_equal(const char *first, const char *second)
{
	unsigned char left[4096];
	unsigned char right[4096];
	struct stat left_status;
	struct stat right_status;
	int left_fd = -1;
	int right_fd = -1;
	int result = 0;

	left_fd = open(first, O_RDONLY | O_CLOEXEC);
	right_fd = open(second, O_RDONLY | O_CLOEXEC);
	if (left_fd < 0 || right_fd < 0 ||
	    fstat(left_fd, &left_status) != 0 ||
	    fstat(right_fd, &right_status) != 0 ||
	    !S_ISREG(left_status.st_mode) ||
	    !S_ISREG(right_status.st_mode) ||
	    left_status.st_size != right_status.st_size)
		goto done;
	for (;;) {
		ssize_t left_size = read_retry(left_fd, left, sizeof left);
		ssize_t right_size = read_retry(right_fd, right, sizeof right);
		if (left_size < 0 || right_size < 0 || left_size != right_size)
			goto done;
		if (left_size == 0) {
			result = 1;
			break;
		}
		if (memcmp(left, right, (size_t) left_size) != 0)
			goto done;
	}

done:
	if (left_fd >= 0)
		close(left_fd);
	if (right_fd >= 0)
		close(right_fd);
	return result;
}

static int install_resources(const char *resources, const char *data)
{
	char bundled[PATH_MAX];
	char installed[PATH_MAX];
	char bundled_version[PATH_MAX];
	char installed_version[PATH_MAX];
	bool refresh;
	size_t index;

	if (path_printf(bundled_version, sizeof bundled_version, "%s/%s",
	    resources, "RESOURCE_VERSION") != 0 ||
	    path_printf(installed_version, sizeof installed_version, "%s/%s",
	    data, ".resource-version") != 0)
		return -1;
	refresh = !files_equal(bundled_version, installed_version);

	for (index = 0;
	    index < sizeof static_resources / sizeof static_resources[0];
	    index++) {
		if (path_printf(bundled, sizeof bundled, "%s/%s", resources,
		    static_resources[index]) != 0 ||
		    path_printf(installed, sizeof installed, "%s/%s", data,
		    static_resources[index]) != 0)
			return -1;
		if ((refresh || !files_equal(bundled, installed)) &&
		    copy_file_atomic(bundled, installed) != 0)
			return -1;
	}

	for (index = 0;
	    index < sizeof mutable_seeds / sizeof mutable_seeds[0];
	    index++) {
		struct stat status;
		if (path_printf(bundled, sizeof bundled, "%s/%s", resources,
		    mutable_seeds[index]) != 0 ||
		    path_printf(installed, sizeof installed, "%s/%s", data,
		    mutable_seeds[index]) != 0)
			return -1;
		if (lstat(installed, &status) != 0) {
			if (errno != ENOENT || copy_file_atomic(bundled, installed) != 0)
				return -1;
		} else if (!S_ISREG(status.st_mode)) {
			errno = EINVAL;
			return -1;
		}
	}

	if (refresh && copy_file_atomic(bundled_version, installed_version) != 0)
		return -1;
	return 0;
}

static int bundle_paths(char *resources, char *game)
{
	char raw[PATH_MAX];
	char launcher[PATH_MAX];
	char macos[PATH_MAX];
	char contents[PATH_MAX];
	char *separator;
	uint32_t size = sizeof raw;

	if (_NSGetExecutablePath(raw, &size) != 0 ||
	    realpath(raw, launcher) == NULL)
		return -1;
	strcpy(macos, launcher);
	separator = strrchr(macos, '/');
	if (separator == NULL)
		return -1;
	*separator = '\0';
	strcpy(contents, macos);
	separator = strrchr(contents, '/');
	if (separator == NULL)
		return -1;
	*separator = '\0';
	if (path_printf(resources, PATH_MAX, "%s/%s", contents,
	    "Resources") != 0 ||
	    path_printf(game, PATH_MAX, "%s/%s", macos,
	    "Noctis-IV.game") != 0)
		return -1;
	return 0;
}

static int data_path(char *data)
{
	const char *override = getenv("NOCTIS_DATA_DIR");
	const char *home;
	struct passwd *account;

	if (override != NULL && override[0] != '\0') {
		if (override[0] != '/' || strlen(override) >= PATH_MAX) {
			errno = EINVAL;
			return -1;
		}
		strcpy(data, override);
		return 0;
	}
	home = getenv("HOME");
	if (home == NULL || home[0] != '/') {
		account = getpwuid(getuid());
		home = account != NULL ? account->pw_dir : NULL;
	}
	if (home == NULL || home[0] != '/') {
		errno = ENOENT;
		return -1;
	}
	return path_printf(data, PATH_MAX,
	    "%s/Library/Application Support/%s", home, "Noctis IV");
}

int main(int argc, char **argv)
{
	char resources[PATH_MAX];
	char game[PATH_MAX];
	char data[PATH_MAX];
	char **game_argv;
	bool prepare_only = false;
	int source;
	int destination = 1;

	if (bundle_paths(resources, game) != 0 || data_path(data) != 0 ||
	    make_directories(data) != 0 || install_resources(resources, data) != 0) {
		fprintf(stderr, "Noctis IV launcher: %s\n", strerror(errno));
		return EXIT_FAILURE;
	}

	game_argv = calloc((size_t) argc + 1, sizeof *game_argv);
	if (game_argv == NULL) {
		fprintf(stderr, "Noctis IV launcher: out of memory\n");
		return EXIT_FAILURE;
	}
	game_argv[0] = game;
	for (source = 1; source < argc; source++) {
		if (strcmp(argv[source], "--launcher-prepare-only") == 0) {
			prepare_only = true;
			continue;
		}
		game_argv[destination++] = argv[source];
	}
	game_argv[destination] = NULL;

	if (prepare_only) {
		printf("NOCTIS_DATA_DIR=%s\n", data);
		free(game_argv);
		return EXIT_SUCCESS;
	}
	if (chdir(data) != 0 || access(game, X_OK) != 0) {
		fprintf(stderr, "Noctis IV launcher: %s\n", strerror(errno));
		free(game_argv);
		return EXIT_FAILURE;
	}
	execv(game, game_argv);
	fprintf(stderr, "Noctis IV launcher: could not start game: %s\n",
	    strerror(errno));
	free(game_argv);
	return EXIT_FAILURE;
}
