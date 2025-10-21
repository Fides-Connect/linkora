///
//  Generated code. Do not modify.
//  source: cloud_tts.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,deprecated_member_use_from_same_package,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:core' as $core;
import 'dart:convert' as $convert;
import 'dart:typed_data' as $typed_data;
@$core.Deprecated('Use ssmlVoiceGenderDescriptor instead')
const SsmlVoiceGender$json = const {
  '1': 'SsmlVoiceGender',
  '2': const [
    const {'1': 'SSML_VOICE_GENDER_UNSPECIFIED', '2': 0},
    const {'1': 'MALE', '2': 1},
    const {'1': 'FEMALE', '2': 2},
    const {'1': 'NEUTRAL', '2': 3},
  ],
};

/// Descriptor for `SsmlVoiceGender`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List ssmlVoiceGenderDescriptor = $convert.base64Decode('Cg9Tc21sVm9pY2VHZW5kZXISIQodU1NNTF9WT0lDRV9HRU5ERVJfVU5TUEVDSUZJRUQQABIICgRNQUxFEAESCgoGRkVNQUxFEAISCwoHTkVVVFJBTBAD');
@$core.Deprecated('Use audioEncodingDescriptor instead')
const AudioEncoding$json = const {
  '1': 'AudioEncoding',
  '2': const [
    const {'1': 'AUDIO_ENCODING_UNSPECIFIED', '2': 0},
    const {'1': 'LINEAR16', '2': 1},
    const {'1': 'MP3', '2': 2},
    const {'1': 'OGG_OPUS', '2': 3},
    const {'1': 'MULAW', '2': 5},
    const {'1': 'ALAW', '2': 6},
    const {'1': 'PCM', '2': 7},
    const {'1': 'M4A', '2': 8},
  ],
};

/// Descriptor for `AudioEncoding`. Decode as a `google.protobuf.EnumDescriptorProto`.
final $typed_data.Uint8List audioEncodingDescriptor = $convert.base64Decode('Cg1BdWRpb0VuY29kaW5nEh4KGkFVRElPX0VOQ09ESU5HX1VOU1BFQ0lGSUVEEAASDAoITElORUFSMTYQARIHCgNNUDMQAhIMCghPR0dfT1BVUxADEgkKBU1VTEFXEAUSCAoEQUxBVxAGEgcKA1BDTRAHEgcKA000QRAI');
@$core.Deprecated('Use listVoicesRequestDescriptor instead')
const ListVoicesRequest$json = const {
  '1': 'ListVoicesRequest',
  '2': const [
    const {'1': 'language_code', '3': 1, '4': 1, '5': 9, '8': const {}, '10': 'languageCode'},
  ],
};

/// Descriptor for `ListVoicesRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List listVoicesRequestDescriptor = $convert.base64Decode('ChFMaXN0Vm9pY2VzUmVxdWVzdBIoCg1sYW5ndWFnZV9jb2RlGAEgASgJQgPgQQFSDGxhbmd1YWdlQ29kZQ==');
@$core.Deprecated('Use listVoicesResponseDescriptor instead')
const ListVoicesResponse$json = const {
  '1': 'ListVoicesResponse',
  '2': const [
    const {'1': 'voices', '3': 1, '4': 3, '5': 11, '6': '.google.cloud.texttospeech.v1.Voice', '10': 'voices'},
  ],
};

/// Descriptor for `ListVoicesResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List listVoicesResponseDescriptor = $convert.base64Decode('ChJMaXN0Vm9pY2VzUmVzcG9uc2USOwoGdm9pY2VzGAEgAygLMiMuZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5Wb2ljZVIGdm9pY2Vz');
@$core.Deprecated('Use voiceDescriptor instead')
const Voice$json = const {
  '1': 'Voice',
  '2': const [
    const {'1': 'language_codes', '3': 1, '4': 3, '5': 9, '10': 'languageCodes'},
    const {'1': 'name', '3': 2, '4': 1, '5': 9, '10': 'name'},
    const {'1': 'ssml_gender', '3': 3, '4': 1, '5': 14, '6': '.google.cloud.texttospeech.v1.SsmlVoiceGender', '10': 'ssmlGender'},
    const {'1': 'natural_sample_rate_hertz', '3': 4, '4': 1, '5': 5, '10': 'naturalSampleRateHertz'},
  ],
};

/// Descriptor for `Voice`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List voiceDescriptor = $convert.base64Decode('CgVWb2ljZRIlCg5sYW5ndWFnZV9jb2RlcxgBIAMoCVINbGFuZ3VhZ2VDb2RlcxISCgRuYW1lGAIgASgJUgRuYW1lEk4KC3NzbWxfZ2VuZGVyGAMgASgOMi0uZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5Tc21sVm9pY2VHZW5kZXJSCnNzbWxHZW5kZXISOQoZbmF0dXJhbF9zYW1wbGVfcmF0ZV9oZXJ0ehgEIAEoBVIWbmF0dXJhbFNhbXBsZVJhdGVIZXJ0eg==');
@$core.Deprecated('Use advancedVoiceOptionsDescriptor instead')
const AdvancedVoiceOptions$json = const {
  '1': 'AdvancedVoiceOptions',
  '2': const [
    const {'1': 'low_latency_journey_synthesis', '3': 1, '4': 1, '5': 8, '9': 0, '10': 'lowLatencyJourneySynthesis', '17': true},
    const {'1': 'relax_safety_filters', '3': 8, '4': 1, '5': 8, '8': const {}, '10': 'relaxSafetyFilters'},
  ],
  '8': const [
    const {'1': '_low_latency_journey_synthesis'},
  ],
};

/// Descriptor for `AdvancedVoiceOptions`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List advancedVoiceOptionsDescriptor = $convert.base64Decode('ChRBZHZhbmNlZFZvaWNlT3B0aW9ucxJGCh1sb3dfbGF0ZW5jeV9qb3VybmV5X3N5bnRoZXNpcxgBIAEoCEgAUhpsb3dMYXRlbmN5Sm91cm5leVN5bnRoZXNpc4gBARI4ChRyZWxheF9zYWZldHlfZmlsdGVycxgIIAEoCEIG4EEE4EEBUhJyZWxheFNhZmV0eUZpbHRlcnNCIAoeX2xvd19sYXRlbmN5X2pvdXJuZXlfc3ludGhlc2lz');
@$core.Deprecated('Use synthesizeSpeechRequestDescriptor instead')
const SynthesizeSpeechRequest$json = const {
  '1': 'SynthesizeSpeechRequest',
  '2': const [
    const {'1': 'input', '3': 1, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.SynthesisInput', '8': const {}, '10': 'input'},
    const {'1': 'voice', '3': 2, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.VoiceSelectionParams', '8': const {}, '10': 'voice'},
    const {'1': 'audio_config', '3': 3, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.AudioConfig', '8': const {}, '10': 'audioConfig'},
    const {'1': 'advanced_voice_options', '3': 8, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.AdvancedVoiceOptions', '9': 0, '10': 'advancedVoiceOptions', '17': true},
  ],
  '8': const [
    const {'1': '_advanced_voice_options'},
  ],
};

/// Descriptor for `SynthesizeSpeechRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List synthesizeSpeechRequestDescriptor = $convert.base64Decode('ChdTeW50aGVzaXplU3BlZWNoUmVxdWVzdBJHCgVpbnB1dBgBIAEoCzIsLmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuU3ludGhlc2lzSW5wdXRCA+BBAlIFaW5wdXQSTQoFdm9pY2UYAiABKAsyMi5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLlZvaWNlU2VsZWN0aW9uUGFyYW1zQgPgQQJSBXZvaWNlElEKDGF1ZGlvX2NvbmZpZxgDIAEoCzIpLmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuQXVkaW9Db25maWdCA+BBAlILYXVkaW9Db25maWcSbQoWYWR2YW5jZWRfdm9pY2Vfb3B0aW9ucxgIIAEoCzIyLmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuQWR2YW5jZWRWb2ljZU9wdGlvbnNIAFIUYWR2YW5jZWRWb2ljZU9wdGlvbnOIAQFCGQoXX2FkdmFuY2VkX3ZvaWNlX29wdGlvbnM=');
@$core.Deprecated('Use customPronunciationParamsDescriptor instead')
const CustomPronunciationParams$json = const {
  '1': 'CustomPronunciationParams',
  '2': const [
    const {'1': 'phrase', '3': 1, '4': 1, '5': 9, '9': 0, '10': 'phrase', '17': true},
    const {'1': 'phonetic_encoding', '3': 2, '4': 1, '5': 14, '6': '.google.cloud.texttospeech.v1.CustomPronunciationParams.PhoneticEncoding', '9': 1, '10': 'phoneticEncoding', '17': true},
    const {'1': 'pronunciation', '3': 3, '4': 1, '5': 9, '9': 2, '10': 'pronunciation', '17': true},
  ],
  '4': const [CustomPronunciationParams_PhoneticEncoding$json],
  '8': const [
    const {'1': '_phrase'},
    const {'1': '_phonetic_encoding'},
    const {'1': '_pronunciation'},
  ],
};

@$core.Deprecated('Use customPronunciationParamsDescriptor instead')
const CustomPronunciationParams_PhoneticEncoding$json = const {
  '1': 'PhoneticEncoding',
  '2': const [
    const {'1': 'PHONETIC_ENCODING_UNSPECIFIED', '2': 0},
    const {'1': 'PHONETIC_ENCODING_IPA', '2': 1},
    const {'1': 'PHONETIC_ENCODING_X_SAMPA', '2': 2},
    const {'1': 'PHONETIC_ENCODING_JAPANESE_YOMIGANA', '2': 3},
    const {'1': 'PHONETIC_ENCODING_PINYIN', '2': 4},
  ],
};

/// Descriptor for `CustomPronunciationParams`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List customPronunciationParamsDescriptor = $convert.base64Decode('ChlDdXN0b21Qcm9udW5jaWF0aW9uUGFyYW1zEhsKBnBocmFzZRgBIAEoCUgAUgZwaHJhc2WIAQESegoRcGhvbmV0aWNfZW5jb2RpbmcYAiABKA4ySC5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLkN1c3RvbVByb251bmNpYXRpb25QYXJhbXMuUGhvbmV0aWNFbmNvZGluZ0gBUhBwaG9uZXRpY0VuY29kaW5niAEBEikKDXByb251bmNpYXRpb24YAyABKAlIAlINcHJvbnVuY2lhdGlvbogBASK2AQoQUGhvbmV0aWNFbmNvZGluZxIhCh1QSE9ORVRJQ19FTkNPRElOR19VTlNQRUNJRklFRBAAEhkKFVBIT05FVElDX0VOQ09ESU5HX0lQQRABEh0KGVBIT05FVElDX0VOQ09ESU5HX1hfU0FNUEEQAhInCiNQSE9ORVRJQ19FTkNPRElOR19KQVBBTkVTRV9ZT01JR0FOQRADEhwKGFBIT05FVElDX0VOQ09ESU5HX1BJTllJThAEQgkKB19waHJhc2VCFAoSX3Bob25ldGljX2VuY29kaW5nQhAKDl9wcm9udW5jaWF0aW9u');
@$core.Deprecated('Use customPronunciationsDescriptor instead')
const CustomPronunciations$json = const {
  '1': 'CustomPronunciations',
  '2': const [
    const {'1': 'pronunciations', '3': 1, '4': 3, '5': 11, '6': '.google.cloud.texttospeech.v1.CustomPronunciationParams', '10': 'pronunciations'},
  ],
};

/// Descriptor for `CustomPronunciations`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List customPronunciationsDescriptor = $convert.base64Decode('ChRDdXN0b21Qcm9udW5jaWF0aW9ucxJfCg5wcm9udW5jaWF0aW9ucxgBIAMoCzI3Lmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuQ3VzdG9tUHJvbnVuY2lhdGlvblBhcmFtc1IOcHJvbnVuY2lhdGlvbnM=');
@$core.Deprecated('Use multiSpeakerMarkupDescriptor instead')
const MultiSpeakerMarkup$json = const {
  '1': 'MultiSpeakerMarkup',
  '2': const [
    const {'1': 'turns', '3': 1, '4': 3, '5': 11, '6': '.google.cloud.texttospeech.v1.MultiSpeakerMarkup.Turn', '8': const {}, '10': 'turns'},
  ],
  '3': const [MultiSpeakerMarkup_Turn$json],
};

@$core.Deprecated('Use multiSpeakerMarkupDescriptor instead')
const MultiSpeakerMarkup_Turn$json = const {
  '1': 'Turn',
  '2': const [
    const {'1': 'speaker', '3': 1, '4': 1, '5': 9, '8': const {}, '10': 'speaker'},
    const {'1': 'text', '3': 2, '4': 1, '5': 9, '8': const {}, '10': 'text'},
  ],
};

/// Descriptor for `MultiSpeakerMarkup`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List multiSpeakerMarkupDescriptor = $convert.base64Decode('ChJNdWx0aVNwZWFrZXJNYXJrdXASUAoFdHVybnMYASADKAsyNS5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLk11bHRpU3BlYWtlck1hcmt1cC5UdXJuQgPgQQJSBXR1cm5zGj4KBFR1cm4SHQoHc3BlYWtlchgBIAEoCUID4EECUgdzcGVha2VyEhcKBHRleHQYAiABKAlCA+BBAlIEdGV4dA==');
@$core.Deprecated('Use multispeakerPrebuiltVoiceDescriptor instead')
const MultispeakerPrebuiltVoice$json = const {
  '1': 'MultispeakerPrebuiltVoice',
  '2': const [
    const {'1': 'speaker_alias', '3': 1, '4': 1, '5': 9, '8': const {}, '10': 'speakerAlias'},
    const {'1': 'speaker_id', '3': 2, '4': 1, '5': 9, '8': const {}, '10': 'speakerId'},
  ],
};

/// Descriptor for `MultispeakerPrebuiltVoice`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List multispeakerPrebuiltVoiceDescriptor = $convert.base64Decode('ChlNdWx0aXNwZWFrZXJQcmVidWlsdFZvaWNlEigKDXNwZWFrZXJfYWxpYXMYASABKAlCA+BBAlIMc3BlYWtlckFsaWFzEiIKCnNwZWFrZXJfaWQYAiABKAlCA+BBAlIJc3BlYWtlcklk');
@$core.Deprecated('Use multiSpeakerVoiceConfigDescriptor instead')
const MultiSpeakerVoiceConfig$json = const {
  '1': 'MultiSpeakerVoiceConfig',
  '2': const [
    const {'1': 'speaker_voice_configs', '3': 2, '4': 3, '5': 11, '6': '.google.cloud.texttospeech.v1.MultispeakerPrebuiltVoice', '8': const {}, '10': 'speakerVoiceConfigs'},
  ],
};

/// Descriptor for `MultiSpeakerVoiceConfig`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List multiSpeakerVoiceConfigDescriptor = $convert.base64Decode('ChdNdWx0aVNwZWFrZXJWb2ljZUNvbmZpZxJwChVzcGVha2VyX3ZvaWNlX2NvbmZpZ3MYAiADKAsyNy5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLk11bHRpc3BlYWtlclByZWJ1aWx0Vm9pY2VCA+BBAlITc3BlYWtlclZvaWNlQ29uZmlncw==');
@$core.Deprecated('Use synthesisInputDescriptor instead')
const SynthesisInput$json = const {
  '1': 'SynthesisInput',
  '2': const [
    const {'1': 'text', '3': 1, '4': 1, '5': 9, '9': 0, '10': 'text'},
    const {'1': 'markup', '3': 5, '4': 1, '5': 9, '9': 0, '10': 'markup'},
    const {'1': 'ssml', '3': 2, '4': 1, '5': 9, '9': 0, '10': 'ssml'},
    const {'1': 'multi_speaker_markup', '3': 4, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.MultiSpeakerMarkup', '9': 0, '10': 'multiSpeakerMarkup'},
    const {'1': 'prompt', '3': 6, '4': 1, '5': 9, '9': 1, '10': 'prompt', '17': true},
    const {'1': 'custom_pronunciations', '3': 3, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.CustomPronunciations', '8': const {}, '10': 'customPronunciations'},
  ],
  '8': const [
    const {'1': 'input_source'},
    const {'1': '_prompt'},
  ],
};

/// Descriptor for `SynthesisInput`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List synthesisInputDescriptor = $convert.base64Decode('Cg5TeW50aGVzaXNJbnB1dBIUCgR0ZXh0GAEgASgJSABSBHRleHQSGAoGbWFya3VwGAUgASgJSABSBm1hcmt1cBIUCgRzc21sGAIgASgJSABSBHNzbWwSZAoUbXVsdGlfc3BlYWtlcl9tYXJrdXAYBCABKAsyMC5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLk11bHRpU3BlYWtlck1hcmt1cEgAUhJtdWx0aVNwZWFrZXJNYXJrdXASGwoGcHJvbXB0GAYgASgJSAFSBnByb21wdIgBARJsChVjdXN0b21fcHJvbnVuY2lhdGlvbnMYAyABKAsyMi5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLkN1c3RvbVByb251bmNpYXRpb25zQgPgQQFSFGN1c3RvbVByb251bmNpYXRpb25zQg4KDGlucHV0X3NvdXJjZUIJCgdfcHJvbXB0');
@$core.Deprecated('Use voiceSelectionParamsDescriptor instead')
const VoiceSelectionParams$json = const {
  '1': 'VoiceSelectionParams',
  '2': const [
    const {'1': 'language_code', '3': 1, '4': 1, '5': 9, '8': const {}, '10': 'languageCode'},
    const {'1': 'name', '3': 2, '4': 1, '5': 9, '10': 'name'},
    const {'1': 'ssml_gender', '3': 3, '4': 1, '5': 14, '6': '.google.cloud.texttospeech.v1.SsmlVoiceGender', '10': 'ssmlGender'},
    const {'1': 'custom_voice', '3': 4, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.CustomVoiceParams', '10': 'customVoice'},
    const {'1': 'voice_clone', '3': 5, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.VoiceCloneParams', '8': const {}, '10': 'voiceClone'},
    const {'1': 'model_name', '3': 6, '4': 1, '5': 9, '8': const {}, '10': 'modelName'},
    const {'1': 'multi_speaker_voice_config', '3': 7, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.MultiSpeakerVoiceConfig', '8': const {}, '10': 'multiSpeakerVoiceConfig'},
  ],
};

/// Descriptor for `VoiceSelectionParams`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List voiceSelectionParamsDescriptor = $convert.base64Decode('ChRWb2ljZVNlbGVjdGlvblBhcmFtcxIoCg1sYW5ndWFnZV9jb2RlGAEgASgJQgPgQQJSDGxhbmd1YWdlQ29kZRISCgRuYW1lGAIgASgJUgRuYW1lEk4KC3NzbWxfZ2VuZGVyGAMgASgOMi0uZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5Tc21sVm9pY2VHZW5kZXJSCnNzbWxHZW5kZXISUgoMY3VzdG9tX3ZvaWNlGAQgASgLMi8uZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5DdXN0b21Wb2ljZVBhcmFtc1ILY3VzdG9tVm9pY2USVAoLdm9pY2VfY2xvbmUYBSABKAsyLi5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLlZvaWNlQ2xvbmVQYXJhbXNCA+BBAVIKdm9pY2VDbG9uZRIiCgptb2RlbF9uYW1lGAYgASgJQgPgQQFSCW1vZGVsTmFtZRJ3ChptdWx0aV9zcGVha2VyX3ZvaWNlX2NvbmZpZxgHIAEoCzI1Lmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuTXVsdGlTcGVha2VyVm9pY2VDb25maWdCA+BBAVIXbXVsdGlTcGVha2VyVm9pY2VDb25maWc=');
@$core.Deprecated('Use audioConfigDescriptor instead')
const AudioConfig$json = const {
  '1': 'AudioConfig',
  '2': const [
    const {'1': 'audio_encoding', '3': 1, '4': 1, '5': 14, '6': '.google.cloud.texttospeech.v1.AudioEncoding', '8': const {}, '10': 'audioEncoding'},
    const {'1': 'speaking_rate', '3': 2, '4': 1, '5': 1, '8': const {}, '10': 'speakingRate'},
    const {'1': 'pitch', '3': 3, '4': 1, '5': 1, '8': const {}, '10': 'pitch'},
    const {'1': 'volume_gain_db', '3': 4, '4': 1, '5': 1, '8': const {}, '10': 'volumeGainDb'},
    const {'1': 'sample_rate_hertz', '3': 5, '4': 1, '5': 5, '8': const {}, '10': 'sampleRateHertz'},
    const {'1': 'effects_profile_id', '3': 6, '4': 3, '5': 9, '8': const {}, '10': 'effectsProfileId'},
  ],
};

/// Descriptor for `AudioConfig`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List audioConfigDescriptor = $convert.base64Decode('CgtBdWRpb0NvbmZpZxJXCg5hdWRpb19lbmNvZGluZxgBIAEoDjIrLmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuQXVkaW9FbmNvZGluZ0ID4EECUg1hdWRpb0VuY29kaW5nEisKDXNwZWFraW5nX3JhdGUYAiABKAFCBuBBBOBBAVIMc3BlYWtpbmdSYXRlEhwKBXBpdGNoGAMgASgBQgbgQQTgQQFSBXBpdGNoEiwKDnZvbHVtZV9nYWluX2RiGAQgASgBQgbgQQTgQQFSDHZvbHVtZUdhaW5EYhIvChFzYW1wbGVfcmF0ZV9oZXJ0ehgFIAEoBUID4EEBUg9zYW1wbGVSYXRlSGVydHoSNAoSZWZmZWN0c19wcm9maWxlX2lkGAYgAygJQgbgQQTgQQFSEGVmZmVjdHNQcm9maWxlSWQ=');
@$core.Deprecated('Use customVoiceParamsDescriptor instead')
const CustomVoiceParams$json = const {
  '1': 'CustomVoiceParams',
  '2': const [
    const {'1': 'model', '3': 1, '4': 1, '5': 9, '8': const {}, '10': 'model'},
    const {
      '1': 'reported_usage',
      '3': 3,
      '4': 1,
      '5': 14,
      '6': '.google.cloud.texttospeech.v1.CustomVoiceParams.ReportedUsage',
      '8': const {'3': true},
      '10': 'reportedUsage',
    },
  ],
  '4': const [CustomVoiceParams_ReportedUsage$json],
};

@$core.Deprecated('Use customVoiceParamsDescriptor instead')
const CustomVoiceParams_ReportedUsage$json = const {
  '1': 'ReportedUsage',
  '2': const [
    const {'1': 'REPORTED_USAGE_UNSPECIFIED', '2': 0},
    const {'1': 'REALTIME', '2': 1},
    const {'1': 'OFFLINE', '2': 2},
  ],
};

/// Descriptor for `CustomVoiceParams`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List customVoiceParamsDescriptor = $convert.base64Decode('ChFDdXN0b21Wb2ljZVBhcmFtcxI5CgVtb2RlbBgBIAEoCUIj4EEC+kEdChthdXRvbWwuZ29vZ2xlYXBpcy5jb20vTW9kZWxSBW1vZGVsEmsKDnJlcG9ydGVkX3VzYWdlGAMgASgOMj0uZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5DdXN0b21Wb2ljZVBhcmFtcy5SZXBvcnRlZFVzYWdlQgUYAeBBAVINcmVwb3J0ZWRVc2FnZSJKCg1SZXBvcnRlZFVzYWdlEh4KGlJFUE9SVEVEX1VTQUdFX1VOU1BFQ0lGSUVEEAASDAoIUkVBTFRJTUUQARILCgdPRkZMSU5FEAI=');
@$core.Deprecated('Use voiceCloneParamsDescriptor instead')
const VoiceCloneParams$json = const {
  '1': 'VoiceCloneParams',
  '2': const [
    const {'1': 'voice_cloning_key', '3': 1, '4': 1, '5': 9, '8': const {}, '10': 'voiceCloningKey'},
  ],
};

/// Descriptor for `VoiceCloneParams`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List voiceCloneParamsDescriptor = $convert.base64Decode('ChBWb2ljZUNsb25lUGFyYW1zEi8KEXZvaWNlX2Nsb25pbmdfa2V5GAEgASgJQgPgQQJSD3ZvaWNlQ2xvbmluZ0tleQ==');
@$core.Deprecated('Use synthesizeSpeechResponseDescriptor instead')
const SynthesizeSpeechResponse$json = const {
  '1': 'SynthesizeSpeechResponse',
  '2': const [
    const {'1': 'audio_content', '3': 1, '4': 1, '5': 12, '10': 'audioContent'},
  ],
};

/// Descriptor for `SynthesizeSpeechResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List synthesizeSpeechResponseDescriptor = $convert.base64Decode('ChhTeW50aGVzaXplU3BlZWNoUmVzcG9uc2USIwoNYXVkaW9fY29udGVudBgBIAEoDFIMYXVkaW9Db250ZW50');
@$core.Deprecated('Use streamingAudioConfigDescriptor instead')
const StreamingAudioConfig$json = const {
  '1': 'StreamingAudioConfig',
  '2': const [
    const {'1': 'audio_encoding', '3': 1, '4': 1, '5': 14, '6': '.google.cloud.texttospeech.v1.AudioEncoding', '8': const {}, '10': 'audioEncoding'},
    const {'1': 'sample_rate_hertz', '3': 2, '4': 1, '5': 5, '8': const {}, '10': 'sampleRateHertz'},
    const {'1': 'speaking_rate', '3': 3, '4': 1, '5': 1, '8': const {}, '10': 'speakingRate'},
  ],
};

/// Descriptor for `StreamingAudioConfig`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List streamingAudioConfigDescriptor = $convert.base64Decode('ChRTdHJlYW1pbmdBdWRpb0NvbmZpZxJXCg5hdWRpb19lbmNvZGluZxgBIAEoDjIrLmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuQXVkaW9FbmNvZGluZ0ID4EECUg1hdWRpb0VuY29kaW5nEi8KEXNhbXBsZV9yYXRlX2hlcnR6GAIgASgFQgPgQQFSD3NhbXBsZVJhdGVIZXJ0ehIrCg1zcGVha2luZ19yYXRlGAMgASgBQgbgQQTgQQFSDHNwZWFraW5nUmF0ZQ==');
@$core.Deprecated('Use streamingSynthesizeConfigDescriptor instead')
const StreamingSynthesizeConfig$json = const {
  '1': 'StreamingSynthesizeConfig',
  '2': const [
    const {'1': 'voice', '3': 1, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.VoiceSelectionParams', '8': const {}, '10': 'voice'},
    const {'1': 'streaming_audio_config', '3': 4, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.StreamingAudioConfig', '8': const {}, '10': 'streamingAudioConfig'},
    const {'1': 'custom_pronunciations', '3': 5, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.CustomPronunciations', '8': const {}, '10': 'customPronunciations'},
  ],
};

/// Descriptor for `StreamingSynthesizeConfig`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List streamingSynthesizeConfigDescriptor = $convert.base64Decode('ChlTdHJlYW1pbmdTeW50aGVzaXplQ29uZmlnEk0KBXZvaWNlGAEgASgLMjIuZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5Wb2ljZVNlbGVjdGlvblBhcmFtc0ID4EECUgV2b2ljZRJtChZzdHJlYW1pbmdfYXVkaW9fY29uZmlnGAQgASgLMjIuZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5TdHJlYW1pbmdBdWRpb0NvbmZpZ0ID4EEBUhRzdHJlYW1pbmdBdWRpb0NvbmZpZxJsChVjdXN0b21fcHJvbnVuY2lhdGlvbnMYBSABKAsyMi5nb29nbGUuY2xvdWQudGV4dHRvc3BlZWNoLnYxLkN1c3RvbVByb251bmNpYXRpb25zQgPgQQFSFGN1c3RvbVByb251bmNpYXRpb25z');
@$core.Deprecated('Use streamingSynthesisInputDescriptor instead')
const StreamingSynthesisInput$json = const {
  '1': 'StreamingSynthesisInput',
  '2': const [
    const {'1': 'text', '3': 1, '4': 1, '5': 9, '9': 0, '10': 'text'},
    const {'1': 'markup', '3': 5, '4': 1, '5': 9, '9': 0, '10': 'markup'},
    const {'1': 'multi_speaker_markup', '3': 7, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.MultiSpeakerMarkup', '9': 0, '10': 'multiSpeakerMarkup'},
    const {'1': 'prompt', '3': 6, '4': 1, '5': 9, '9': 1, '10': 'prompt', '17': true},
  ],
  '8': const [
    const {'1': 'input_source'},
    const {'1': '_prompt'},
  ],
};

/// Descriptor for `StreamingSynthesisInput`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List streamingSynthesisInputDescriptor = $convert.base64Decode('ChdTdHJlYW1pbmdTeW50aGVzaXNJbnB1dBIUCgR0ZXh0GAEgASgJSABSBHRleHQSGAoGbWFya3VwGAUgASgJSABSBm1hcmt1cBJkChRtdWx0aV9zcGVha2VyX21hcmt1cBgHIAEoCzIwLmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuTXVsdGlTcGVha2VyTWFya3VwSABSEm11bHRpU3BlYWtlck1hcmt1cBIbCgZwcm9tcHQYBiABKAlIAVIGcHJvbXB0iAEBQg4KDGlucHV0X3NvdXJjZUIJCgdfcHJvbXB0');
@$core.Deprecated('Use streamingSynthesizeRequestDescriptor instead')
const StreamingSynthesizeRequest$json = const {
  '1': 'StreamingSynthesizeRequest',
  '2': const [
    const {'1': 'streaming_config', '3': 1, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.StreamingSynthesizeConfig', '9': 0, '10': 'streamingConfig'},
    const {'1': 'input', '3': 2, '4': 1, '5': 11, '6': '.google.cloud.texttospeech.v1.StreamingSynthesisInput', '9': 0, '10': 'input'},
  ],
  '8': const [
    const {'1': 'streaming_request'},
  ],
};

/// Descriptor for `StreamingSynthesizeRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List streamingSynthesizeRequestDescriptor = $convert.base64Decode('ChpTdHJlYW1pbmdTeW50aGVzaXplUmVxdWVzdBJkChBzdHJlYW1pbmdfY29uZmlnGAEgASgLMjcuZ29vZ2xlLmNsb3VkLnRleHR0b3NwZWVjaC52MS5TdHJlYW1pbmdTeW50aGVzaXplQ29uZmlnSABSD3N0cmVhbWluZ0NvbmZpZxJNCgVpbnB1dBgCIAEoCzI1Lmdvb2dsZS5jbG91ZC50ZXh0dG9zcGVlY2gudjEuU3RyZWFtaW5nU3ludGhlc2lzSW5wdXRIAFIFaW5wdXRCEwoRc3RyZWFtaW5nX3JlcXVlc3Q=');
@$core.Deprecated('Use streamingSynthesizeResponseDescriptor instead')
const StreamingSynthesizeResponse$json = const {
  '1': 'StreamingSynthesizeResponse',
  '2': const [
    const {'1': 'audio_content', '3': 1, '4': 1, '5': 12, '10': 'audioContent'},
  ],
};

/// Descriptor for `StreamingSynthesizeResponse`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List streamingSynthesizeResponseDescriptor = $convert.base64Decode('ChtTdHJlYW1pbmdTeW50aGVzaXplUmVzcG9uc2USIwoNYXVkaW9fY29udGVudBgBIAEoDFIMYXVkaW9Db250ZW50');
