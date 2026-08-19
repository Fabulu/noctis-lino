#ifndef LINO_HEADLESS
#include <AudioToolbox/AudioToolbox.h>
#include <stdatomic.h>
#include <stdint.h>
#endif

#include "lino_sound.h"

#ifdef LINO_HEADLESS

bool lino_sound_init(void)
{
	pUIWorkspace[mm_PCMdataStatus] = 0;
	pUIWorkspace[mm_PCMdataCHannels] = 0;
	pUIWorkspace[mm_PCMdataBitsPerSample] = 0;
	pUIWorkspace[mm_PCMdataSamplesPerSec] = 0;
	pUIWorkspace[mm_PCMdataSilenceThreshold] = 0;
	pUIWorkspace[mm_PCMdataOffset] = 0;
	return true;
}

bool lino_sound_close(void)
{
	return true;
}

bool krnlPCMdataCommand(PCMdataCommand command)
{
	return command == IDLE;
}

#else

#define LINO_AUDIO_CHANNELS 2
#define LINO_AUDIO_BITS 16
#define LINO_AUDIO_RATE 44100
#define LINO_AUDIO_BYTES_PER_FRAME 4
#define LINO_AUDIO_BUFFERS 3
#define LINO_AUDIO_BUFFER_BYTES 16384

typedef enum {
	LINO_AUDIO_ERROR = -1,
	LINO_AUDIO_END,
	LINO_AUDIO_QUEUED
} lino_audio_fill_result;

typedef struct {
	AudioQueueRef queue;
	unsigned char *data;
	uint64_t frames;
	uint64_t next_frame;
	bool continuous;
	atomic_bool callback_error;
} lino_audio_state;

static lino_audio_state audioState;

static AudioStreamBasicDescription lino_audio_format(void)
{
	AudioStreamBasicDescription format;

	memset(&format, 0, sizeof format);
	format.mSampleRate = LINO_AUDIO_RATE;
	format.mFormatID = kAudioFormatLinearPCM;
	format.mFormatFlags = kAudioFormatFlagIsSignedInteger |
	    kAudioFormatFlagIsPacked;
	format.mBytesPerPacket = LINO_AUDIO_BYTES_PER_FRAME;
	format.mFramesPerPacket = 1;
	format.mBytesPerFrame = LINO_AUDIO_BYTES_PER_FRAME;
	format.mChannelsPerFrame = LINO_AUDIO_CHANNELS;
	format.mBitsPerChannel = LINO_AUDIO_BITS;
	return format;
}

static lino_audio_fill_result lino_audio_fill(AudioQueueBufferRef buffer)
{
	uint64_t capacity = buffer->mAudioDataBytesCapacity /
	    LINO_AUDIO_BYTES_PER_FRAME;
	uint64_t written = 0;

	while (written < capacity && audioState.frames > 0) {
		uint64_t available;
		uint64_t take;

		if (audioState.next_frame >= audioState.frames) {
			if (!audioState.continuous)
				break;
			audioState.next_frame = 0;
		}
		available = audioState.frames - audioState.next_frame;
		take = capacity - written;
		if (take > available)
			take = available;
		memcpy((unsigned char *) buffer->mAudioData +
		       written * LINO_AUDIO_BYTES_PER_FRAME,
		       audioState.data +
		       audioState.next_frame * LINO_AUDIO_BYTES_PER_FRAME,
		       (size_t) take * LINO_AUDIO_BYTES_PER_FRAME);
		audioState.next_frame += take;
		written += take;
	}

	buffer->mAudioDataByteSize =
	    (UInt32) (written * LINO_AUDIO_BYTES_PER_FRAME);
	if (written == 0)
		return LINO_AUDIO_END;
	if (AudioQueueEnqueueBuffer(audioState.queue, buffer, 0, NULL) != noErr) {
		atomic_store(&audioState.callback_error, true);
		return LINO_AUDIO_ERROR;
	}
	return LINO_AUDIO_QUEUED;
}

static void lino_audio_callback(void *context, AudioQueueRef queue,
    AudioQueueBufferRef buffer)
{
	(void) context;
	(void) queue;
	lino_audio_fill(buffer);
}

static bool lino_audio_stop(void)
{
	AudioQueueRef queue = audioState.queue;
	unsigned char *data = audioState.data;
	OSStatus stop_status = noErr;

	if (queue != NULL) {
		stop_status = AudioQueueStop(queue, true);
		if (AudioQueueDispose(queue, true) != noErr) {
			/* The queue can still call back, so retain everything it sees. */
			atomic_store(&audioState.callback_error, true);
			return false;
		}
	}
	audioState.queue = NULL;
	audioState.data = NULL;
	audioState.frames = 0;
	audioState.next_frame = 0;
	audioState.continuous = false;
	atomic_store(&audioState.callback_error, false);
	free(data);
	if (pUIWorkspace != NULL) {
		pUIWorkspace[mm_PCMdataStatus] = PCMREADY;
		pUIWorkspace[mm_PCMdataOffset] = 0;
	}
	return stop_status == noErr;
}

static bool lino_audio_play(bool continuous)
{
	AudioStreamBasicDescription format = lino_audio_format();
	AudioQueueRef queue = NULL;
	unit origin = pUIWorkspace[mm_PCMdataOrigin];
	unit frames = pUIWorkspace[mm_PCMdataSize];
	uint64_t end;
	int index;

	if (origin < 0 || frames <= 0 || current_ramtop < 0)
		return false;
	end = (uint64_t) (uint32_t) origin + (uint64_t) (uint32_t) frames;
	if (end > (uint64_t) (uint32_t) current_ramtop ||
	    (uint64_t) (uint32_t) frames > SIZE_MAX / LINO_AUDIO_BYTES_PER_FRAME)
		return false;

	if (!lino_audio_stop())
		return false;
	audioState.data = malloc((size_t) frames * LINO_AUDIO_BYTES_PER_FRAME);
	if (audioState.data == NULL)
		return false;
	memcpy(audioState.data, &pWorkspace[origin],
	    (size_t) frames * LINO_AUDIO_BYTES_PER_FRAME);
	audioState.frames = (uint32_t) frames;
	audioState.continuous = continuous;

	if (AudioQueueNewOutput(&format, lino_audio_callback, &audioState,
	    NULL, NULL, 0, &queue) != noErr) {
		lino_audio_stop();
		return false;
	}
	audioState.queue = queue;
	for (index = 0; index < LINO_AUDIO_BUFFERS; index++) {
		AudioQueueBufferRef buffer;
		lino_audio_fill_result fill_result;
		if (AudioQueueAllocateBuffer(queue, LINO_AUDIO_BUFFER_BYTES,
		    &buffer) != noErr) {
			lino_audio_stop();
			return false;
		}
		fill_result = lino_audio_fill(buffer);
		if (fill_result == LINO_AUDIO_ERROR) {
			lino_audio_stop();
			return false;
		}
		if (fill_result == LINO_AUDIO_END) {
			if (index == 0) {
				lino_audio_stop();
				return false;
			}
			break;
		}
	}
	if (AudioQueueStart(queue, NULL) != noErr) {
		lino_audio_stop();
		return false;
	}
	pUIWorkspace[mm_PCMdataStatus] = PCMREADY;
	pUIWorkspace[mm_PCMdataOffset] = 0;
	return true;
}

static bool lino_audio_update_offset(void)
{
	AudioTimeStamp stamp;
	Boolean discontinuity = false;
	uint64_t offset;

	if (audioState.queue == NULL || audioState.frames == 0) {
		pUIWorkspace[mm_PCMdataOffset] = 0;
		return true;
	}
	if (AudioQueueGetCurrentTime(audioState.queue, NULL, &stamp,
	    &discontinuity) != noErr || !(stamp.mFlags & kAudioTimeStampSampleTimeValid))
		return false;
	if (stamp.mSampleTime <= 0)
		offset = 0;
	else
		offset = (uint64_t) stamp.mSampleTime;
	if (audioState.continuous)
		offset %= audioState.frames;
	else if (offset > audioState.frames)
		offset = audioState.frames;
	pUIWorkspace[mm_PCMdataOffset] = (unit) offset;
	return true;
}

bool lino_sound_init(void)
{
	AudioStreamBasicDescription format = lino_audio_format();
	AudioQueueRef probe = NULL;

	memset(&audioState, 0, sizeof audioState);
	atomic_init(&audioState.callback_error, false);
	pUIWorkspace[mm_PCMdataStatus] = 0;
	pUIWorkspace[mm_PCMdataCHannels] = LINO_AUDIO_CHANNELS;
	pUIWorkspace[mm_PCMdataBitsPerSample] = LINO_AUDIO_BITS;
	pUIWorkspace[mm_PCMdataSamplesPerSec] = LINO_AUDIO_RATE;
	pUIWorkspace[mm_PCMdataSilenceThreshold] = 0;
	pUIWorkspace[mm_PCMdataOffset] = 0;
	if (AudioQueueNewOutput(&format, lino_audio_callback, &audioState,
	    NULL, NULL, 0, &probe) != noErr)
		return false;
	if (AudioQueueDispose(probe, true) != noErr)
		return false;
	pUIWorkspace[mm_PCMdataStatus] = PCMREADY;
	return true;
}

bool lino_sound_close(void)
{
	bool closed = lino_audio_stop();
	if (pUIWorkspace != NULL)
		pUIWorkspace[mm_PCMdataStatus] = 0;
	return closed;
}

/**
 * handles all PCM commands.
 * @return false when errors, true otherwise
 */
bool krnlPCMdataCommand(PCMdataCommand command)
{
	if (atomic_exchange(&audioState.callback_error, false)) {
		lino_audio_stop();
		return false;
	}
	switch (command) {
	case IDLE:
		break;
	case GETDATAOFFSET:
		return lino_audio_update_offset();
	case PLAYONCE:
		return lino_audio_play(false);
	case PLAYCONTINUOUSLY:
		return lino_audio_play(true);
	case _PAUSE:
		if (audioState.queue == NULL ||
		    AudioQueuePause(audioState.queue) != noErr)
			return false;
		pUIWorkspace[mm_PCMdataStatus] = PCMREADY | PCMPAUSED;
		break;
	case _UNPAUSE:
		if (audioState.queue == NULL ||
		    AudioQueueStart(audioState.queue, NULL) != noErr)
			return false;
		pUIWorkspace[mm_PCMdataStatus] = PCMREADY;
		break;
	case _STOP:
		return lino_audio_stop();
	default:
		return false;
	}
	return true;
}

#endif
