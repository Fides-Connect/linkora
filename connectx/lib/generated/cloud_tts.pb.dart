///
//  Generated code. Do not modify.
//  source: cloud_tts.proto
//
// @dart = 2.12
// ignore_for_file: annotate_overrides,camel_case_types,constant_identifier_names,directives_ordering,library_prefixes,non_constant_identifier_names,prefer_final_fields,return_of_invalid_type,unnecessary_const,unnecessary_import,unnecessary_this,unused_import,unused_shown_name

import 'dart:core' as $core;

import 'package:protobuf/protobuf.dart' as $pb;

import 'cloud_tts.pbenum.dart';

export 'cloud_tts.pbenum.dart';

class ListVoicesRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'ListVoicesRequest', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'languageCode')
    ..hasRequiredFields = false
  ;

  ListVoicesRequest._() : super();
  factory ListVoicesRequest({
    $core.String? languageCode,
  }) {
    final _result = create();
    if (languageCode != null) {
      _result.languageCode = languageCode;
    }
    return _result;
  }
  factory ListVoicesRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ListVoicesRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ListVoicesRequest clone() => ListVoicesRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ListVoicesRequest copyWith(void Function(ListVoicesRequest) updates) => super.copyWith((message) => updates(message as ListVoicesRequest)) as ListVoicesRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static ListVoicesRequest create() => ListVoicesRequest._();
  ListVoicesRequest createEmptyInstance() => create();
  static $pb.PbList<ListVoicesRequest> createRepeated() => $pb.PbList<ListVoicesRequest>();
  @$core.pragma('dart2js:noInline')
  static ListVoicesRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ListVoicesRequest>(create);
  static ListVoicesRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get languageCode => $_getSZ(0);
  @$pb.TagNumber(1)
  set languageCode($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasLanguageCode() => $_has(0);
  @$pb.TagNumber(1)
  void clearLanguageCode() => clearField(1);
}

class ListVoicesResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'ListVoicesResponse', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..pc<Voice>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voices', $pb.PbFieldType.PM, subBuilder: Voice.create)
    ..hasRequiredFields = false
  ;

  ListVoicesResponse._() : super();
  factory ListVoicesResponse({
    $core.Iterable<Voice>? voices,
  }) {
    final _result = create();
    if (voices != null) {
      _result.voices.addAll(voices);
    }
    return _result;
  }
  factory ListVoicesResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ListVoicesResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ListVoicesResponse clone() => ListVoicesResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ListVoicesResponse copyWith(void Function(ListVoicesResponse) updates) => super.copyWith((message) => updates(message as ListVoicesResponse)) as ListVoicesResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static ListVoicesResponse create() => ListVoicesResponse._();
  ListVoicesResponse createEmptyInstance() => create();
  static $pb.PbList<ListVoicesResponse> createRepeated() => $pb.PbList<ListVoicesResponse>();
  @$core.pragma('dart2js:noInline')
  static ListVoicesResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ListVoicesResponse>(create);
  static ListVoicesResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<Voice> get voices => $_getList(0);
}

class Voice extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'Voice', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..pPS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'languageCodes')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'name')
    ..e<SsmlVoiceGender>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'ssmlGender', $pb.PbFieldType.OE, defaultOrMaker: SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED, valueOf: SsmlVoiceGender.valueOf, enumValues: SsmlVoiceGender.values)
    ..a<$core.int>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'naturalSampleRateHertz', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  Voice._() : super();
  factory Voice({
    $core.Iterable<$core.String>? languageCodes,
    $core.String? name,
    SsmlVoiceGender? ssmlGender,
    $core.int? naturalSampleRateHertz,
  }) {
    final _result = create();
    if (languageCodes != null) {
      _result.languageCodes.addAll(languageCodes);
    }
    if (name != null) {
      _result.name = name;
    }
    if (ssmlGender != null) {
      _result.ssmlGender = ssmlGender;
    }
    if (naturalSampleRateHertz != null) {
      _result.naturalSampleRateHertz = naturalSampleRateHertz;
    }
    return _result;
  }
  factory Voice.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Voice.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Voice clone() => Voice()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Voice copyWith(void Function(Voice) updates) => super.copyWith((message) => updates(message as Voice)) as Voice; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static Voice create() => Voice._();
  Voice createEmptyInstance() => create();
  static $pb.PbList<Voice> createRepeated() => $pb.PbList<Voice>();
  @$core.pragma('dart2js:noInline')
  static Voice getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Voice>(create);
  static Voice? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<$core.String> get languageCodes => $_getList(0);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => clearField(2);

  @$pb.TagNumber(3)
  SsmlVoiceGender get ssmlGender => $_getN(2);
  @$pb.TagNumber(3)
  set ssmlGender(SsmlVoiceGender v) { setField(3, v); }
  @$pb.TagNumber(3)
  $core.bool hasSsmlGender() => $_has(2);
  @$pb.TagNumber(3)
  void clearSsmlGender() => clearField(3);

  @$pb.TagNumber(4)
  $core.int get naturalSampleRateHertz => $_getIZ(3);
  @$pb.TagNumber(4)
  set naturalSampleRateHertz($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasNaturalSampleRateHertz() => $_has(3);
  @$pb.TagNumber(4)
  void clearNaturalSampleRateHertz() => clearField(4);
}

class AdvancedVoiceOptions extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AdvancedVoiceOptions', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOB(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'lowLatencyJourneySynthesis')
    ..aOB(8, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'relaxSafetyFilters')
    ..hasRequiredFields = false
  ;

  AdvancedVoiceOptions._() : super();
  factory AdvancedVoiceOptions({
    $core.bool? lowLatencyJourneySynthesis,
    $core.bool? relaxSafetyFilters,
  }) {
    final _result = create();
    if (lowLatencyJourneySynthesis != null) {
      _result.lowLatencyJourneySynthesis = lowLatencyJourneySynthesis;
    }
    if (relaxSafetyFilters != null) {
      _result.relaxSafetyFilters = relaxSafetyFilters;
    }
    return _result;
  }
  factory AdvancedVoiceOptions.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AdvancedVoiceOptions.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AdvancedVoiceOptions clone() => AdvancedVoiceOptions()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AdvancedVoiceOptions copyWith(void Function(AdvancedVoiceOptions) updates) => super.copyWith((message) => updates(message as AdvancedVoiceOptions)) as AdvancedVoiceOptions; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AdvancedVoiceOptions create() => AdvancedVoiceOptions._();
  AdvancedVoiceOptions createEmptyInstance() => create();
  static $pb.PbList<AdvancedVoiceOptions> createRepeated() => $pb.PbList<AdvancedVoiceOptions>();
  @$core.pragma('dart2js:noInline')
  static AdvancedVoiceOptions getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AdvancedVoiceOptions>(create);
  static AdvancedVoiceOptions? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get lowLatencyJourneySynthesis => $_getBF(0);
  @$pb.TagNumber(1)
  set lowLatencyJourneySynthesis($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasLowLatencyJourneySynthesis() => $_has(0);
  @$pb.TagNumber(1)
  void clearLowLatencyJourneySynthesis() => clearField(1);

  @$pb.TagNumber(8)
  $core.bool get relaxSafetyFilters => $_getBF(1);
  @$pb.TagNumber(8)
  set relaxSafetyFilters($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(8)
  $core.bool hasRelaxSafetyFilters() => $_has(1);
  @$pb.TagNumber(8)
  void clearRelaxSafetyFilters() => clearField(8);
}

class SynthesizeSpeechRequest extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'SynthesizeSpeechRequest', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOM<SynthesisInput>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'input', subBuilder: SynthesisInput.create)
    ..aOM<VoiceSelectionParams>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voice', subBuilder: VoiceSelectionParams.create)
    ..aOM<AudioConfig>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'audioConfig', subBuilder: AudioConfig.create)
    ..aOM<AdvancedVoiceOptions>(8, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'advancedVoiceOptions', subBuilder: AdvancedVoiceOptions.create)
    ..hasRequiredFields = false
  ;

  SynthesizeSpeechRequest._() : super();
  factory SynthesizeSpeechRequest({
    SynthesisInput? input,
    VoiceSelectionParams? voice,
    AudioConfig? audioConfig,
    AdvancedVoiceOptions? advancedVoiceOptions,
  }) {
    final _result = create();
    if (input != null) {
      _result.input = input;
    }
    if (voice != null) {
      _result.voice = voice;
    }
    if (audioConfig != null) {
      _result.audioConfig = audioConfig;
    }
    if (advancedVoiceOptions != null) {
      _result.advancedVoiceOptions = advancedVoiceOptions;
    }
    return _result;
  }
  factory SynthesizeSpeechRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory SynthesizeSpeechRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  SynthesizeSpeechRequest clone() => SynthesizeSpeechRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  SynthesizeSpeechRequest copyWith(void Function(SynthesizeSpeechRequest) updates) => super.copyWith((message) => updates(message as SynthesizeSpeechRequest)) as SynthesizeSpeechRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static SynthesizeSpeechRequest create() => SynthesizeSpeechRequest._();
  SynthesizeSpeechRequest createEmptyInstance() => create();
  static $pb.PbList<SynthesizeSpeechRequest> createRepeated() => $pb.PbList<SynthesizeSpeechRequest>();
  @$core.pragma('dart2js:noInline')
  static SynthesizeSpeechRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<SynthesizeSpeechRequest>(create);
  static SynthesizeSpeechRequest? _defaultInstance;

  @$pb.TagNumber(1)
  SynthesisInput get input => $_getN(0);
  @$pb.TagNumber(1)
  set input(SynthesisInput v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasInput() => $_has(0);
  @$pb.TagNumber(1)
  void clearInput() => clearField(1);
  @$pb.TagNumber(1)
  SynthesisInput ensureInput() => $_ensure(0);

  @$pb.TagNumber(2)
  VoiceSelectionParams get voice => $_getN(1);
  @$pb.TagNumber(2)
  set voice(VoiceSelectionParams v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasVoice() => $_has(1);
  @$pb.TagNumber(2)
  void clearVoice() => clearField(2);
  @$pb.TagNumber(2)
  VoiceSelectionParams ensureVoice() => $_ensure(1);

  @$pb.TagNumber(3)
  AudioConfig get audioConfig => $_getN(2);
  @$pb.TagNumber(3)
  set audioConfig(AudioConfig v) { setField(3, v); }
  @$pb.TagNumber(3)
  $core.bool hasAudioConfig() => $_has(2);
  @$pb.TagNumber(3)
  void clearAudioConfig() => clearField(3);
  @$pb.TagNumber(3)
  AudioConfig ensureAudioConfig() => $_ensure(2);

  @$pb.TagNumber(8)
  AdvancedVoiceOptions get advancedVoiceOptions => $_getN(3);
  @$pb.TagNumber(8)
  set advancedVoiceOptions(AdvancedVoiceOptions v) { setField(8, v); }
  @$pb.TagNumber(8)
  $core.bool hasAdvancedVoiceOptions() => $_has(3);
  @$pb.TagNumber(8)
  void clearAdvancedVoiceOptions() => clearField(8);
  @$pb.TagNumber(8)
  AdvancedVoiceOptions ensureAdvancedVoiceOptions() => $_ensure(3);
}

class CustomPronunciationParams extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'CustomPronunciationParams', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'phrase')
    ..e<CustomPronunciationParams_PhoneticEncoding>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'phoneticEncoding', $pb.PbFieldType.OE, defaultOrMaker: CustomPronunciationParams_PhoneticEncoding.PHONETIC_ENCODING_UNSPECIFIED, valueOf: CustomPronunciationParams_PhoneticEncoding.valueOf, enumValues: CustomPronunciationParams_PhoneticEncoding.values)
    ..aOS(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pronunciation')
    ..hasRequiredFields = false
  ;

  CustomPronunciationParams._() : super();
  factory CustomPronunciationParams({
    $core.String? phrase,
    CustomPronunciationParams_PhoneticEncoding? phoneticEncoding,
    $core.String? pronunciation,
  }) {
    final _result = create();
    if (phrase != null) {
      _result.phrase = phrase;
    }
    if (phoneticEncoding != null) {
      _result.phoneticEncoding = phoneticEncoding;
    }
    if (pronunciation != null) {
      _result.pronunciation = pronunciation;
    }
    return _result;
  }
  factory CustomPronunciationParams.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CustomPronunciationParams.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CustomPronunciationParams clone() => CustomPronunciationParams()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CustomPronunciationParams copyWith(void Function(CustomPronunciationParams) updates) => super.copyWith((message) => updates(message as CustomPronunciationParams)) as CustomPronunciationParams; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static CustomPronunciationParams create() => CustomPronunciationParams._();
  CustomPronunciationParams createEmptyInstance() => create();
  static $pb.PbList<CustomPronunciationParams> createRepeated() => $pb.PbList<CustomPronunciationParams>();
  @$core.pragma('dart2js:noInline')
  static CustomPronunciationParams getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CustomPronunciationParams>(create);
  static CustomPronunciationParams? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get phrase => $_getSZ(0);
  @$pb.TagNumber(1)
  set phrase($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPhrase() => $_has(0);
  @$pb.TagNumber(1)
  void clearPhrase() => clearField(1);

  @$pb.TagNumber(2)
  CustomPronunciationParams_PhoneticEncoding get phoneticEncoding => $_getN(1);
  @$pb.TagNumber(2)
  set phoneticEncoding(CustomPronunciationParams_PhoneticEncoding v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasPhoneticEncoding() => $_has(1);
  @$pb.TagNumber(2)
  void clearPhoneticEncoding() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get pronunciation => $_getSZ(2);
  @$pb.TagNumber(3)
  set pronunciation($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasPronunciation() => $_has(2);
  @$pb.TagNumber(3)
  void clearPronunciation() => clearField(3);
}

class CustomPronunciations extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'CustomPronunciations', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..pc<CustomPronunciationParams>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pronunciations', $pb.PbFieldType.PM, subBuilder: CustomPronunciationParams.create)
    ..hasRequiredFields = false
  ;

  CustomPronunciations._() : super();
  factory CustomPronunciations({
    $core.Iterable<CustomPronunciationParams>? pronunciations,
  }) {
    final _result = create();
    if (pronunciations != null) {
      _result.pronunciations.addAll(pronunciations);
    }
    return _result;
  }
  factory CustomPronunciations.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CustomPronunciations.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CustomPronunciations clone() => CustomPronunciations()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CustomPronunciations copyWith(void Function(CustomPronunciations) updates) => super.copyWith((message) => updates(message as CustomPronunciations)) as CustomPronunciations; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static CustomPronunciations create() => CustomPronunciations._();
  CustomPronunciations createEmptyInstance() => create();
  static $pb.PbList<CustomPronunciations> createRepeated() => $pb.PbList<CustomPronunciations>();
  @$core.pragma('dart2js:noInline')
  static CustomPronunciations getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CustomPronunciations>(create);
  static CustomPronunciations? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<CustomPronunciationParams> get pronunciations => $_getList(0);
}

class MultiSpeakerMarkup_Turn extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'MultiSpeakerMarkup.Turn', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'speaker')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'text')
    ..hasRequiredFields = false
  ;

  MultiSpeakerMarkup_Turn._() : super();
  factory MultiSpeakerMarkup_Turn({
    $core.String? speaker,
    $core.String? text,
  }) {
    final _result = create();
    if (speaker != null) {
      _result.speaker = speaker;
    }
    if (text != null) {
      _result.text = text;
    }
    return _result;
  }
  factory MultiSpeakerMarkup_Turn.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory MultiSpeakerMarkup_Turn.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  MultiSpeakerMarkup_Turn clone() => MultiSpeakerMarkup_Turn()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  MultiSpeakerMarkup_Turn copyWith(void Function(MultiSpeakerMarkup_Turn) updates) => super.copyWith((message) => updates(message as MultiSpeakerMarkup_Turn)) as MultiSpeakerMarkup_Turn; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static MultiSpeakerMarkup_Turn create() => MultiSpeakerMarkup_Turn._();
  MultiSpeakerMarkup_Turn createEmptyInstance() => create();
  static $pb.PbList<MultiSpeakerMarkup_Turn> createRepeated() => $pb.PbList<MultiSpeakerMarkup_Turn>();
  @$core.pragma('dart2js:noInline')
  static MultiSpeakerMarkup_Turn getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<MultiSpeakerMarkup_Turn>(create);
  static MultiSpeakerMarkup_Turn? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get speaker => $_getSZ(0);
  @$pb.TagNumber(1)
  set speaker($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSpeaker() => $_has(0);
  @$pb.TagNumber(1)
  void clearSpeaker() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get text => $_getSZ(1);
  @$pb.TagNumber(2)
  set text($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasText() => $_has(1);
  @$pb.TagNumber(2)
  void clearText() => clearField(2);
}

class MultiSpeakerMarkup extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'MultiSpeakerMarkup', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..pc<MultiSpeakerMarkup_Turn>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'turns', $pb.PbFieldType.PM, subBuilder: MultiSpeakerMarkup_Turn.create)
    ..hasRequiredFields = false
  ;

  MultiSpeakerMarkup._() : super();
  factory MultiSpeakerMarkup({
    $core.Iterable<MultiSpeakerMarkup_Turn>? turns,
  }) {
    final _result = create();
    if (turns != null) {
      _result.turns.addAll(turns);
    }
    return _result;
  }
  factory MultiSpeakerMarkup.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory MultiSpeakerMarkup.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  MultiSpeakerMarkup clone() => MultiSpeakerMarkup()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  MultiSpeakerMarkup copyWith(void Function(MultiSpeakerMarkup) updates) => super.copyWith((message) => updates(message as MultiSpeakerMarkup)) as MultiSpeakerMarkup; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static MultiSpeakerMarkup create() => MultiSpeakerMarkup._();
  MultiSpeakerMarkup createEmptyInstance() => create();
  static $pb.PbList<MultiSpeakerMarkup> createRepeated() => $pb.PbList<MultiSpeakerMarkup>();
  @$core.pragma('dart2js:noInline')
  static MultiSpeakerMarkup getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<MultiSpeakerMarkup>(create);
  static MultiSpeakerMarkup? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<MultiSpeakerMarkup_Turn> get turns => $_getList(0);
}

class MultispeakerPrebuiltVoice extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'MultispeakerPrebuiltVoice', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'speakerAlias')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'speakerId')
    ..hasRequiredFields = false
  ;

  MultispeakerPrebuiltVoice._() : super();
  factory MultispeakerPrebuiltVoice({
    $core.String? speakerAlias,
    $core.String? speakerId,
  }) {
    final _result = create();
    if (speakerAlias != null) {
      _result.speakerAlias = speakerAlias;
    }
    if (speakerId != null) {
      _result.speakerId = speakerId;
    }
    return _result;
  }
  factory MultispeakerPrebuiltVoice.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory MultispeakerPrebuiltVoice.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  MultispeakerPrebuiltVoice clone() => MultispeakerPrebuiltVoice()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  MultispeakerPrebuiltVoice copyWith(void Function(MultispeakerPrebuiltVoice) updates) => super.copyWith((message) => updates(message as MultispeakerPrebuiltVoice)) as MultispeakerPrebuiltVoice; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static MultispeakerPrebuiltVoice create() => MultispeakerPrebuiltVoice._();
  MultispeakerPrebuiltVoice createEmptyInstance() => create();
  static $pb.PbList<MultispeakerPrebuiltVoice> createRepeated() => $pb.PbList<MultispeakerPrebuiltVoice>();
  @$core.pragma('dart2js:noInline')
  static MultispeakerPrebuiltVoice getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<MultispeakerPrebuiltVoice>(create);
  static MultispeakerPrebuiltVoice? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get speakerAlias => $_getSZ(0);
  @$pb.TagNumber(1)
  set speakerAlias($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSpeakerAlias() => $_has(0);
  @$pb.TagNumber(1)
  void clearSpeakerAlias() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get speakerId => $_getSZ(1);
  @$pb.TagNumber(2)
  set speakerId($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasSpeakerId() => $_has(1);
  @$pb.TagNumber(2)
  void clearSpeakerId() => clearField(2);
}

class MultiSpeakerVoiceConfig extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'MultiSpeakerVoiceConfig', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..pc<MultispeakerPrebuiltVoice>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'speakerVoiceConfigs', $pb.PbFieldType.PM, subBuilder: MultispeakerPrebuiltVoice.create)
    ..hasRequiredFields = false
  ;

  MultiSpeakerVoiceConfig._() : super();
  factory MultiSpeakerVoiceConfig({
    $core.Iterable<MultispeakerPrebuiltVoice>? speakerVoiceConfigs,
  }) {
    final _result = create();
    if (speakerVoiceConfigs != null) {
      _result.speakerVoiceConfigs.addAll(speakerVoiceConfigs);
    }
    return _result;
  }
  factory MultiSpeakerVoiceConfig.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory MultiSpeakerVoiceConfig.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  MultiSpeakerVoiceConfig clone() => MultiSpeakerVoiceConfig()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  MultiSpeakerVoiceConfig copyWith(void Function(MultiSpeakerVoiceConfig) updates) => super.copyWith((message) => updates(message as MultiSpeakerVoiceConfig)) as MultiSpeakerVoiceConfig; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static MultiSpeakerVoiceConfig create() => MultiSpeakerVoiceConfig._();
  MultiSpeakerVoiceConfig createEmptyInstance() => create();
  static $pb.PbList<MultiSpeakerVoiceConfig> createRepeated() => $pb.PbList<MultiSpeakerVoiceConfig>();
  @$core.pragma('dart2js:noInline')
  static MultiSpeakerVoiceConfig getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<MultiSpeakerVoiceConfig>(create);
  static MultiSpeakerVoiceConfig? _defaultInstance;

  @$pb.TagNumber(2)
  $core.List<MultispeakerPrebuiltVoice> get speakerVoiceConfigs => $_getList(0);
}

enum SynthesisInput_InputSource {
  text, 
  ssml, 
  multiSpeakerMarkup, 
  markup, 
  notSet
}

class SynthesisInput extends $pb.GeneratedMessage {
  static const $core.Map<$core.int, SynthesisInput_InputSource> _SynthesisInput_InputSourceByTag = {
    1 : SynthesisInput_InputSource.text,
    2 : SynthesisInput_InputSource.ssml,
    4 : SynthesisInput_InputSource.multiSpeakerMarkup,
    5 : SynthesisInput_InputSource.markup,
    0 : SynthesisInput_InputSource.notSet
  };
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'SynthesisInput', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..oo(0, [1, 2, 4, 5])
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'text')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'ssml')
    ..aOM<CustomPronunciations>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'customPronunciations', subBuilder: CustomPronunciations.create)
    ..aOM<MultiSpeakerMarkup>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'multiSpeakerMarkup', subBuilder: MultiSpeakerMarkup.create)
    ..aOS(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'markup')
    ..aOS(6, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'prompt')
    ..hasRequiredFields = false
  ;

  SynthesisInput._() : super();
  factory SynthesisInput({
    $core.String? text,
    $core.String? ssml,
    CustomPronunciations? customPronunciations,
    MultiSpeakerMarkup? multiSpeakerMarkup,
    $core.String? markup,
    $core.String? prompt,
  }) {
    final _result = create();
    if (text != null) {
      _result.text = text;
    }
    if (ssml != null) {
      _result.ssml = ssml;
    }
    if (customPronunciations != null) {
      _result.customPronunciations = customPronunciations;
    }
    if (multiSpeakerMarkup != null) {
      _result.multiSpeakerMarkup = multiSpeakerMarkup;
    }
    if (markup != null) {
      _result.markup = markup;
    }
    if (prompt != null) {
      _result.prompt = prompt;
    }
    return _result;
  }
  factory SynthesisInput.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory SynthesisInput.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  SynthesisInput clone() => SynthesisInput()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  SynthesisInput copyWith(void Function(SynthesisInput) updates) => super.copyWith((message) => updates(message as SynthesisInput)) as SynthesisInput; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static SynthesisInput create() => SynthesisInput._();
  SynthesisInput createEmptyInstance() => create();
  static $pb.PbList<SynthesisInput> createRepeated() => $pb.PbList<SynthesisInput>();
  @$core.pragma('dart2js:noInline')
  static SynthesisInput getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<SynthesisInput>(create);
  static SynthesisInput? _defaultInstance;

  SynthesisInput_InputSource whichInputSource() => _SynthesisInput_InputSourceByTag[$_whichOneof(0)]!;
  void clearInputSource() => clearField($_whichOneof(0));

  @$pb.TagNumber(1)
  $core.String get text => $_getSZ(0);
  @$pb.TagNumber(1)
  set text($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasText() => $_has(0);
  @$pb.TagNumber(1)
  void clearText() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get ssml => $_getSZ(1);
  @$pb.TagNumber(2)
  set ssml($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasSsml() => $_has(1);
  @$pb.TagNumber(2)
  void clearSsml() => clearField(2);

  @$pb.TagNumber(3)
  CustomPronunciations get customPronunciations => $_getN(2);
  @$pb.TagNumber(3)
  set customPronunciations(CustomPronunciations v) { setField(3, v); }
  @$pb.TagNumber(3)
  $core.bool hasCustomPronunciations() => $_has(2);
  @$pb.TagNumber(3)
  void clearCustomPronunciations() => clearField(3);
  @$pb.TagNumber(3)
  CustomPronunciations ensureCustomPronunciations() => $_ensure(2);

  @$pb.TagNumber(4)
  MultiSpeakerMarkup get multiSpeakerMarkup => $_getN(3);
  @$pb.TagNumber(4)
  set multiSpeakerMarkup(MultiSpeakerMarkup v) { setField(4, v); }
  @$pb.TagNumber(4)
  $core.bool hasMultiSpeakerMarkup() => $_has(3);
  @$pb.TagNumber(4)
  void clearMultiSpeakerMarkup() => clearField(4);
  @$pb.TagNumber(4)
  MultiSpeakerMarkup ensureMultiSpeakerMarkup() => $_ensure(3);

  @$pb.TagNumber(5)
  $core.String get markup => $_getSZ(4);
  @$pb.TagNumber(5)
  set markup($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasMarkup() => $_has(4);
  @$pb.TagNumber(5)
  void clearMarkup() => clearField(5);

  @$pb.TagNumber(6)
  $core.String get prompt => $_getSZ(5);
  @$pb.TagNumber(6)
  set prompt($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasPrompt() => $_has(5);
  @$pb.TagNumber(6)
  void clearPrompt() => clearField(6);
}

class VoiceSelectionParams extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'VoiceSelectionParams', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'languageCode')
    ..aOS(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'name')
    ..e<SsmlVoiceGender>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'ssmlGender', $pb.PbFieldType.OE, defaultOrMaker: SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED, valueOf: SsmlVoiceGender.valueOf, enumValues: SsmlVoiceGender.values)
    ..aOM<CustomVoiceParams>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'customVoice', subBuilder: CustomVoiceParams.create)
    ..aOM<VoiceCloneParams>(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voiceClone', subBuilder: VoiceCloneParams.create)
    ..aOS(6, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'modelName')
    ..aOM<MultiSpeakerVoiceConfig>(7, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'multiSpeakerVoiceConfig', subBuilder: MultiSpeakerVoiceConfig.create)
    ..hasRequiredFields = false
  ;

  VoiceSelectionParams._() : super();
  factory VoiceSelectionParams({
    $core.String? languageCode,
    $core.String? name,
    SsmlVoiceGender? ssmlGender,
    CustomVoiceParams? customVoice,
    VoiceCloneParams? voiceClone,
    $core.String? modelName,
    MultiSpeakerVoiceConfig? multiSpeakerVoiceConfig,
  }) {
    final _result = create();
    if (languageCode != null) {
      _result.languageCode = languageCode;
    }
    if (name != null) {
      _result.name = name;
    }
    if (ssmlGender != null) {
      _result.ssmlGender = ssmlGender;
    }
    if (customVoice != null) {
      _result.customVoice = customVoice;
    }
    if (voiceClone != null) {
      _result.voiceClone = voiceClone;
    }
    if (modelName != null) {
      _result.modelName = modelName;
    }
    if (multiSpeakerVoiceConfig != null) {
      _result.multiSpeakerVoiceConfig = multiSpeakerVoiceConfig;
    }
    return _result;
  }
  factory VoiceSelectionParams.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory VoiceSelectionParams.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  VoiceSelectionParams clone() => VoiceSelectionParams()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  VoiceSelectionParams copyWith(void Function(VoiceSelectionParams) updates) => super.copyWith((message) => updates(message as VoiceSelectionParams)) as VoiceSelectionParams; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static VoiceSelectionParams create() => VoiceSelectionParams._();
  VoiceSelectionParams createEmptyInstance() => create();
  static $pb.PbList<VoiceSelectionParams> createRepeated() => $pb.PbList<VoiceSelectionParams>();
  @$core.pragma('dart2js:noInline')
  static VoiceSelectionParams getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<VoiceSelectionParams>(create);
  static VoiceSelectionParams? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get languageCode => $_getSZ(0);
  @$pb.TagNumber(1)
  set languageCode($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasLanguageCode() => $_has(0);
  @$pb.TagNumber(1)
  void clearLanguageCode() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => clearField(2);

  @$pb.TagNumber(3)
  SsmlVoiceGender get ssmlGender => $_getN(2);
  @$pb.TagNumber(3)
  set ssmlGender(SsmlVoiceGender v) { setField(3, v); }
  @$pb.TagNumber(3)
  $core.bool hasSsmlGender() => $_has(2);
  @$pb.TagNumber(3)
  void clearSsmlGender() => clearField(3);

  @$pb.TagNumber(4)
  CustomVoiceParams get customVoice => $_getN(3);
  @$pb.TagNumber(4)
  set customVoice(CustomVoiceParams v) { setField(4, v); }
  @$pb.TagNumber(4)
  $core.bool hasCustomVoice() => $_has(3);
  @$pb.TagNumber(4)
  void clearCustomVoice() => clearField(4);
  @$pb.TagNumber(4)
  CustomVoiceParams ensureCustomVoice() => $_ensure(3);

  @$pb.TagNumber(5)
  VoiceCloneParams get voiceClone => $_getN(4);
  @$pb.TagNumber(5)
  set voiceClone(VoiceCloneParams v) { setField(5, v); }
  @$pb.TagNumber(5)
  $core.bool hasVoiceClone() => $_has(4);
  @$pb.TagNumber(5)
  void clearVoiceClone() => clearField(5);
  @$pb.TagNumber(5)
  VoiceCloneParams ensureVoiceClone() => $_ensure(4);

  @$pb.TagNumber(6)
  $core.String get modelName => $_getSZ(5);
  @$pb.TagNumber(6)
  set modelName($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasModelName() => $_has(5);
  @$pb.TagNumber(6)
  void clearModelName() => clearField(6);

  @$pb.TagNumber(7)
  MultiSpeakerVoiceConfig get multiSpeakerVoiceConfig => $_getN(6);
  @$pb.TagNumber(7)
  set multiSpeakerVoiceConfig(MultiSpeakerVoiceConfig v) { setField(7, v); }
  @$pb.TagNumber(7)
  $core.bool hasMultiSpeakerVoiceConfig() => $_has(6);
  @$pb.TagNumber(7)
  void clearMultiSpeakerVoiceConfig() => clearField(7);
  @$pb.TagNumber(7)
  MultiSpeakerVoiceConfig ensureMultiSpeakerVoiceConfig() => $_ensure(6);
}

class AudioConfig extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'AudioConfig', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..e<AudioEncoding>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'audioEncoding', $pb.PbFieldType.OE, defaultOrMaker: AudioEncoding.AUDIO_ENCODING_UNSPECIFIED, valueOf: AudioEncoding.valueOf, enumValues: AudioEncoding.values)
    ..a<$core.double>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'speakingRate', $pb.PbFieldType.OD)
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'pitch', $pb.PbFieldType.OD)
    ..a<$core.double>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'volumeGainDb', $pb.PbFieldType.OD)
    ..a<$core.int>(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'sampleRateHertz', $pb.PbFieldType.O3)
    ..pPS(6, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'effectsProfileId')
    ..hasRequiredFields = false
  ;

  AudioConfig._() : super();
  factory AudioConfig({
    AudioEncoding? audioEncoding,
    $core.double? speakingRate,
    $core.double? pitch,
    $core.double? volumeGainDb,
    $core.int? sampleRateHertz,
    $core.Iterable<$core.String>? effectsProfileId,
  }) {
    final _result = create();
    if (audioEncoding != null) {
      _result.audioEncoding = audioEncoding;
    }
    if (speakingRate != null) {
      _result.speakingRate = speakingRate;
    }
    if (pitch != null) {
      _result.pitch = pitch;
    }
    if (volumeGainDb != null) {
      _result.volumeGainDb = volumeGainDb;
    }
    if (sampleRateHertz != null) {
      _result.sampleRateHertz = sampleRateHertz;
    }
    if (effectsProfileId != null) {
      _result.effectsProfileId.addAll(effectsProfileId);
    }
    return _result;
  }
  factory AudioConfig.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AudioConfig.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AudioConfig clone() => AudioConfig()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AudioConfig copyWith(void Function(AudioConfig) updates) => super.copyWith((message) => updates(message as AudioConfig)) as AudioConfig; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static AudioConfig create() => AudioConfig._();
  AudioConfig createEmptyInstance() => create();
  static $pb.PbList<AudioConfig> createRepeated() => $pb.PbList<AudioConfig>();
  @$core.pragma('dart2js:noInline')
  static AudioConfig getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AudioConfig>(create);
  static AudioConfig? _defaultInstance;

  @$pb.TagNumber(1)
  AudioEncoding get audioEncoding => $_getN(0);
  @$pb.TagNumber(1)
  set audioEncoding(AudioEncoding v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasAudioEncoding() => $_has(0);
  @$pb.TagNumber(1)
  void clearAudioEncoding() => clearField(1);

  @$pb.TagNumber(2)
  $core.double get speakingRate => $_getN(1);
  @$pb.TagNumber(2)
  set speakingRate($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasSpeakingRate() => $_has(1);
  @$pb.TagNumber(2)
  void clearSpeakingRate() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get pitch => $_getN(2);
  @$pb.TagNumber(3)
  set pitch($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasPitch() => $_has(2);
  @$pb.TagNumber(3)
  void clearPitch() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get volumeGainDb => $_getN(3);
  @$pb.TagNumber(4)
  set volumeGainDb($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasVolumeGainDb() => $_has(3);
  @$pb.TagNumber(4)
  void clearVolumeGainDb() => clearField(4);

  @$pb.TagNumber(5)
  $core.int get sampleRateHertz => $_getIZ(4);
  @$pb.TagNumber(5)
  set sampleRateHertz($core.int v) { $_setSignedInt32(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasSampleRateHertz() => $_has(4);
  @$pb.TagNumber(5)
  void clearSampleRateHertz() => clearField(5);

  @$pb.TagNumber(6)
  $core.List<$core.String> get effectsProfileId => $_getList(5);
}

class CustomVoiceParams extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'CustomVoiceParams', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'model')
    ..e<CustomVoiceParams_ReportedUsage>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'reportedUsage', $pb.PbFieldType.OE, defaultOrMaker: CustomVoiceParams_ReportedUsage.REPORTED_USAGE_UNSPECIFIED, valueOf: CustomVoiceParams_ReportedUsage.valueOf, enumValues: CustomVoiceParams_ReportedUsage.values)
    ..hasRequiredFields = false
  ;

  CustomVoiceParams._() : super();
  factory CustomVoiceParams({
    $core.String? model,
  @$core.Deprecated('This field is deprecated.')
    CustomVoiceParams_ReportedUsage? reportedUsage,
  }) {
    final _result = create();
    if (model != null) {
      _result.model = model;
    }
    if (reportedUsage != null) {
      // ignore: deprecated_member_use_from_same_package
      _result.reportedUsage = reportedUsage;
    }
    return _result;
  }
  factory CustomVoiceParams.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CustomVoiceParams.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CustomVoiceParams clone() => CustomVoiceParams()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CustomVoiceParams copyWith(void Function(CustomVoiceParams) updates) => super.copyWith((message) => updates(message as CustomVoiceParams)) as CustomVoiceParams; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static CustomVoiceParams create() => CustomVoiceParams._();
  CustomVoiceParams createEmptyInstance() => create();
  static $pb.PbList<CustomVoiceParams> createRepeated() => $pb.PbList<CustomVoiceParams>();
  @$core.pragma('dart2js:noInline')
  static CustomVoiceParams getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CustomVoiceParams>(create);
  static CustomVoiceParams? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get model => $_getSZ(0);
  @$pb.TagNumber(1)
  set model($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasModel() => $_has(0);
  @$pb.TagNumber(1)
  void clearModel() => clearField(1);

  @$core.Deprecated('This field is deprecated.')
  @$pb.TagNumber(3)
  CustomVoiceParams_ReportedUsage get reportedUsage => $_getN(1);
  @$core.Deprecated('This field is deprecated.')
  @$pb.TagNumber(3)
  set reportedUsage(CustomVoiceParams_ReportedUsage v) { setField(3, v); }
  @$core.Deprecated('This field is deprecated.')
  @$pb.TagNumber(3)
  $core.bool hasReportedUsage() => $_has(1);
  @$core.Deprecated('This field is deprecated.')
  @$pb.TagNumber(3)
  void clearReportedUsage() => clearField(3);
}

class VoiceCloneParams extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'VoiceCloneParams', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voiceCloningKey')
    ..hasRequiredFields = false
  ;

  VoiceCloneParams._() : super();
  factory VoiceCloneParams({
    $core.String? voiceCloningKey,
  }) {
    final _result = create();
    if (voiceCloningKey != null) {
      _result.voiceCloningKey = voiceCloningKey;
    }
    return _result;
  }
  factory VoiceCloneParams.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory VoiceCloneParams.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  VoiceCloneParams clone() => VoiceCloneParams()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  VoiceCloneParams copyWith(void Function(VoiceCloneParams) updates) => super.copyWith((message) => updates(message as VoiceCloneParams)) as VoiceCloneParams; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static VoiceCloneParams create() => VoiceCloneParams._();
  VoiceCloneParams createEmptyInstance() => create();
  static $pb.PbList<VoiceCloneParams> createRepeated() => $pb.PbList<VoiceCloneParams>();
  @$core.pragma('dart2js:noInline')
  static VoiceCloneParams getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<VoiceCloneParams>(create);
  static VoiceCloneParams? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get voiceCloningKey => $_getSZ(0);
  @$pb.TagNumber(1)
  set voiceCloningKey($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasVoiceCloningKey() => $_has(0);
  @$pb.TagNumber(1)
  void clearVoiceCloningKey() => clearField(1);
}

class SynthesizeSpeechResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'SynthesizeSpeechResponse', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..a<$core.List<$core.int>>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'audioContent', $pb.PbFieldType.OY)
    ..hasRequiredFields = false
  ;

  SynthesizeSpeechResponse._() : super();
  factory SynthesizeSpeechResponse({
    $core.List<$core.int>? audioContent,
  }) {
    final _result = create();
    if (audioContent != null) {
      _result.audioContent = audioContent;
    }
    return _result;
  }
  factory SynthesizeSpeechResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory SynthesizeSpeechResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  SynthesizeSpeechResponse clone() => SynthesizeSpeechResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  SynthesizeSpeechResponse copyWith(void Function(SynthesizeSpeechResponse) updates) => super.copyWith((message) => updates(message as SynthesizeSpeechResponse)) as SynthesizeSpeechResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static SynthesizeSpeechResponse create() => SynthesizeSpeechResponse._();
  SynthesizeSpeechResponse createEmptyInstance() => create();
  static $pb.PbList<SynthesizeSpeechResponse> createRepeated() => $pb.PbList<SynthesizeSpeechResponse>();
  @$core.pragma('dart2js:noInline')
  static SynthesizeSpeechResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<SynthesizeSpeechResponse>(create);
  static SynthesizeSpeechResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<$core.int> get audioContent => $_getN(0);
  @$pb.TagNumber(1)
  set audioContent($core.List<$core.int> v) { $_setBytes(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasAudioContent() => $_has(0);
  @$pb.TagNumber(1)
  void clearAudioContent() => clearField(1);
}

class StreamingAudioConfig extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'StreamingAudioConfig', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..e<AudioEncoding>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'audioEncoding', $pb.PbFieldType.OE, defaultOrMaker: AudioEncoding.AUDIO_ENCODING_UNSPECIFIED, valueOf: AudioEncoding.valueOf, enumValues: AudioEncoding.values)
    ..a<$core.int>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'sampleRateHertz', $pb.PbFieldType.O3)
    ..a<$core.double>(3, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'speakingRate', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  StreamingAudioConfig._() : super();
  factory StreamingAudioConfig({
    AudioEncoding? audioEncoding,
    $core.int? sampleRateHertz,
    $core.double? speakingRate,
  }) {
    final _result = create();
    if (audioEncoding != null) {
      _result.audioEncoding = audioEncoding;
    }
    if (sampleRateHertz != null) {
      _result.sampleRateHertz = sampleRateHertz;
    }
    if (speakingRate != null) {
      _result.speakingRate = speakingRate;
    }
    return _result;
  }
  factory StreamingAudioConfig.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory StreamingAudioConfig.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  StreamingAudioConfig clone() => StreamingAudioConfig()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  StreamingAudioConfig copyWith(void Function(StreamingAudioConfig) updates) => super.copyWith((message) => updates(message as StreamingAudioConfig)) as StreamingAudioConfig; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static StreamingAudioConfig create() => StreamingAudioConfig._();
  StreamingAudioConfig createEmptyInstance() => create();
  static $pb.PbList<StreamingAudioConfig> createRepeated() => $pb.PbList<StreamingAudioConfig>();
  @$core.pragma('dart2js:noInline')
  static StreamingAudioConfig getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<StreamingAudioConfig>(create);
  static StreamingAudioConfig? _defaultInstance;

  @$pb.TagNumber(1)
  AudioEncoding get audioEncoding => $_getN(0);
  @$pb.TagNumber(1)
  set audioEncoding(AudioEncoding v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasAudioEncoding() => $_has(0);
  @$pb.TagNumber(1)
  void clearAudioEncoding() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get sampleRateHertz => $_getIZ(1);
  @$pb.TagNumber(2)
  set sampleRateHertz($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasSampleRateHertz() => $_has(1);
  @$pb.TagNumber(2)
  void clearSampleRateHertz() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get speakingRate => $_getN(2);
  @$pb.TagNumber(3)
  set speakingRate($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasSpeakingRate() => $_has(2);
  @$pb.TagNumber(3)
  void clearSpeakingRate() => clearField(3);
}

class StreamingSynthesizeConfig extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'StreamingSynthesizeConfig', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..aOM<VoiceSelectionParams>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'voice', subBuilder: VoiceSelectionParams.create)
    ..aOM<StreamingAudioConfig>(4, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'streamingAudioConfig', subBuilder: StreamingAudioConfig.create)
    ..aOM<CustomPronunciations>(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'customPronunciations', subBuilder: CustomPronunciations.create)
    ..hasRequiredFields = false
  ;

  StreamingSynthesizeConfig._() : super();
  factory StreamingSynthesizeConfig({
    VoiceSelectionParams? voice,
    StreamingAudioConfig? streamingAudioConfig,
    CustomPronunciations? customPronunciations,
  }) {
    final _result = create();
    if (voice != null) {
      _result.voice = voice;
    }
    if (streamingAudioConfig != null) {
      _result.streamingAudioConfig = streamingAudioConfig;
    }
    if (customPronunciations != null) {
      _result.customPronunciations = customPronunciations;
    }
    return _result;
  }
  factory StreamingSynthesizeConfig.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory StreamingSynthesizeConfig.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  StreamingSynthesizeConfig clone() => StreamingSynthesizeConfig()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  StreamingSynthesizeConfig copyWith(void Function(StreamingSynthesizeConfig) updates) => super.copyWith((message) => updates(message as StreamingSynthesizeConfig)) as StreamingSynthesizeConfig; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesizeConfig create() => StreamingSynthesizeConfig._();
  StreamingSynthesizeConfig createEmptyInstance() => create();
  static $pb.PbList<StreamingSynthesizeConfig> createRepeated() => $pb.PbList<StreamingSynthesizeConfig>();
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesizeConfig getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<StreamingSynthesizeConfig>(create);
  static StreamingSynthesizeConfig? _defaultInstance;

  @$pb.TagNumber(1)
  VoiceSelectionParams get voice => $_getN(0);
  @$pb.TagNumber(1)
  set voice(VoiceSelectionParams v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasVoice() => $_has(0);
  @$pb.TagNumber(1)
  void clearVoice() => clearField(1);
  @$pb.TagNumber(1)
  VoiceSelectionParams ensureVoice() => $_ensure(0);

  @$pb.TagNumber(4)
  StreamingAudioConfig get streamingAudioConfig => $_getN(1);
  @$pb.TagNumber(4)
  set streamingAudioConfig(StreamingAudioConfig v) { setField(4, v); }
  @$pb.TagNumber(4)
  $core.bool hasStreamingAudioConfig() => $_has(1);
  @$pb.TagNumber(4)
  void clearStreamingAudioConfig() => clearField(4);
  @$pb.TagNumber(4)
  StreamingAudioConfig ensureStreamingAudioConfig() => $_ensure(1);

  @$pb.TagNumber(5)
  CustomPronunciations get customPronunciations => $_getN(2);
  @$pb.TagNumber(5)
  set customPronunciations(CustomPronunciations v) { setField(5, v); }
  @$pb.TagNumber(5)
  $core.bool hasCustomPronunciations() => $_has(2);
  @$pb.TagNumber(5)
  void clearCustomPronunciations() => clearField(5);
  @$pb.TagNumber(5)
  CustomPronunciations ensureCustomPronunciations() => $_ensure(2);
}

enum StreamingSynthesisInput_InputSource {
  text, 
  markup, 
  multiSpeakerMarkup, 
  notSet
}

class StreamingSynthesisInput extends $pb.GeneratedMessage {
  static const $core.Map<$core.int, StreamingSynthesisInput_InputSource> _StreamingSynthesisInput_InputSourceByTag = {
    1 : StreamingSynthesisInput_InputSource.text,
    5 : StreamingSynthesisInput_InputSource.markup,
    7 : StreamingSynthesisInput_InputSource.multiSpeakerMarkup,
    0 : StreamingSynthesisInput_InputSource.notSet
  };
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'StreamingSynthesisInput', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..oo(0, [1, 5, 7])
    ..aOS(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'text')
    ..aOS(5, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'markup')
    ..aOS(6, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'prompt')
    ..aOM<MultiSpeakerMarkup>(7, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'multiSpeakerMarkup', subBuilder: MultiSpeakerMarkup.create)
    ..hasRequiredFields = false
  ;

  StreamingSynthesisInput._() : super();
  factory StreamingSynthesisInput({
    $core.String? text,
    $core.String? markup,
    $core.String? prompt,
    MultiSpeakerMarkup? multiSpeakerMarkup,
  }) {
    final _result = create();
    if (text != null) {
      _result.text = text;
    }
    if (markup != null) {
      _result.markup = markup;
    }
    if (prompt != null) {
      _result.prompt = prompt;
    }
    if (multiSpeakerMarkup != null) {
      _result.multiSpeakerMarkup = multiSpeakerMarkup;
    }
    return _result;
  }
  factory StreamingSynthesisInput.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory StreamingSynthesisInput.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  StreamingSynthesisInput clone() => StreamingSynthesisInput()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  StreamingSynthesisInput copyWith(void Function(StreamingSynthesisInput) updates) => super.copyWith((message) => updates(message as StreamingSynthesisInput)) as StreamingSynthesisInput; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesisInput create() => StreamingSynthesisInput._();
  StreamingSynthesisInput createEmptyInstance() => create();
  static $pb.PbList<StreamingSynthesisInput> createRepeated() => $pb.PbList<StreamingSynthesisInput>();
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesisInput getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<StreamingSynthesisInput>(create);
  static StreamingSynthesisInput? _defaultInstance;

  StreamingSynthesisInput_InputSource whichInputSource() => _StreamingSynthesisInput_InputSourceByTag[$_whichOneof(0)]!;
  void clearInputSource() => clearField($_whichOneof(0));

  @$pb.TagNumber(1)
  $core.String get text => $_getSZ(0);
  @$pb.TagNumber(1)
  set text($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasText() => $_has(0);
  @$pb.TagNumber(1)
  void clearText() => clearField(1);

  @$pb.TagNumber(5)
  $core.String get markup => $_getSZ(1);
  @$pb.TagNumber(5)
  set markup($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(5)
  $core.bool hasMarkup() => $_has(1);
  @$pb.TagNumber(5)
  void clearMarkup() => clearField(5);

  @$pb.TagNumber(6)
  $core.String get prompt => $_getSZ(2);
  @$pb.TagNumber(6)
  set prompt($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(6)
  $core.bool hasPrompt() => $_has(2);
  @$pb.TagNumber(6)
  void clearPrompt() => clearField(6);

  @$pb.TagNumber(7)
  MultiSpeakerMarkup get multiSpeakerMarkup => $_getN(3);
  @$pb.TagNumber(7)
  set multiSpeakerMarkup(MultiSpeakerMarkup v) { setField(7, v); }
  @$pb.TagNumber(7)
  $core.bool hasMultiSpeakerMarkup() => $_has(3);
  @$pb.TagNumber(7)
  void clearMultiSpeakerMarkup() => clearField(7);
  @$pb.TagNumber(7)
  MultiSpeakerMarkup ensureMultiSpeakerMarkup() => $_ensure(3);
}

enum StreamingSynthesizeRequest_StreamingRequest {
  streamingConfig, 
  input, 
  notSet
}

class StreamingSynthesizeRequest extends $pb.GeneratedMessage {
  static const $core.Map<$core.int, StreamingSynthesizeRequest_StreamingRequest> _StreamingSynthesizeRequest_StreamingRequestByTag = {
    1 : StreamingSynthesizeRequest_StreamingRequest.streamingConfig,
    2 : StreamingSynthesizeRequest_StreamingRequest.input,
    0 : StreamingSynthesizeRequest_StreamingRequest.notSet
  };
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'StreamingSynthesizeRequest', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..oo(0, [1, 2])
    ..aOM<StreamingSynthesizeConfig>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'streamingConfig', subBuilder: StreamingSynthesizeConfig.create)
    ..aOM<StreamingSynthesisInput>(2, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'input', subBuilder: StreamingSynthesisInput.create)
    ..hasRequiredFields = false
  ;

  StreamingSynthesizeRequest._() : super();
  factory StreamingSynthesizeRequest({
    StreamingSynthesizeConfig? streamingConfig,
    StreamingSynthesisInput? input,
  }) {
    final _result = create();
    if (streamingConfig != null) {
      _result.streamingConfig = streamingConfig;
    }
    if (input != null) {
      _result.input = input;
    }
    return _result;
  }
  factory StreamingSynthesizeRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory StreamingSynthesizeRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  StreamingSynthesizeRequest clone() => StreamingSynthesizeRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  StreamingSynthesizeRequest copyWith(void Function(StreamingSynthesizeRequest) updates) => super.copyWith((message) => updates(message as StreamingSynthesizeRequest)) as StreamingSynthesizeRequest; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesizeRequest create() => StreamingSynthesizeRequest._();
  StreamingSynthesizeRequest createEmptyInstance() => create();
  static $pb.PbList<StreamingSynthesizeRequest> createRepeated() => $pb.PbList<StreamingSynthesizeRequest>();
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesizeRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<StreamingSynthesizeRequest>(create);
  static StreamingSynthesizeRequest? _defaultInstance;

  StreamingSynthesizeRequest_StreamingRequest whichStreamingRequest() => _StreamingSynthesizeRequest_StreamingRequestByTag[$_whichOneof(0)]!;
  void clearStreamingRequest() => clearField($_whichOneof(0));

  @$pb.TagNumber(1)
  StreamingSynthesizeConfig get streamingConfig => $_getN(0);
  @$pb.TagNumber(1)
  set streamingConfig(StreamingSynthesizeConfig v) { setField(1, v); }
  @$pb.TagNumber(1)
  $core.bool hasStreamingConfig() => $_has(0);
  @$pb.TagNumber(1)
  void clearStreamingConfig() => clearField(1);
  @$pb.TagNumber(1)
  StreamingSynthesizeConfig ensureStreamingConfig() => $_ensure(0);

  @$pb.TagNumber(2)
  StreamingSynthesisInput get input => $_getN(1);
  @$pb.TagNumber(2)
  set input(StreamingSynthesisInput v) { setField(2, v); }
  @$pb.TagNumber(2)
  $core.bool hasInput() => $_has(1);
  @$pb.TagNumber(2)
  void clearInput() => clearField(2);
  @$pb.TagNumber(2)
  StreamingSynthesisInput ensureInput() => $_ensure(1);
}

class StreamingSynthesizeResponse extends $pb.GeneratedMessage {
  static final $pb.BuilderInfo _i = $pb.BuilderInfo(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'StreamingSynthesizeResponse', package: const $pb.PackageName(const $core.bool.fromEnvironment('protobuf.omit_message_names') ? '' : 'google.cloud.texttospeech.v1'), createEmptyInstance: create)
    ..a<$core.List<$core.int>>(1, const $core.bool.fromEnvironment('protobuf.omit_field_names') ? '' : 'audioContent', $pb.PbFieldType.OY)
    ..hasRequiredFields = false
  ;

  StreamingSynthesizeResponse._() : super();
  factory StreamingSynthesizeResponse({
    $core.List<$core.int>? audioContent,
  }) {
    final _result = create();
    if (audioContent != null) {
      _result.audioContent = audioContent;
    }
    return _result;
  }
  factory StreamingSynthesizeResponse.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory StreamingSynthesizeResponse.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  StreamingSynthesizeResponse clone() => StreamingSynthesizeResponse()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  StreamingSynthesizeResponse copyWith(void Function(StreamingSynthesizeResponse) updates) => super.copyWith((message) => updates(message as StreamingSynthesizeResponse)) as StreamingSynthesizeResponse; // ignore: deprecated_member_use
  $pb.BuilderInfo get info_ => _i;
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesizeResponse create() => StreamingSynthesizeResponse._();
  StreamingSynthesizeResponse createEmptyInstance() => create();
  static $pb.PbList<StreamingSynthesizeResponse> createRepeated() => $pb.PbList<StreamingSynthesizeResponse>();
  @$core.pragma('dart2js:noInline')
  static StreamingSynthesizeResponse getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<StreamingSynthesizeResponse>(create);
  static StreamingSynthesizeResponse? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<$core.int> get audioContent => $_getN(0);
  @$pb.TagNumber(1)
  set audioContent($core.List<$core.int> v) { $_setBytes(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasAudioContent() => $_has(0);
  @$pb.TagNumber(1)
  void clearAudioContent() => clearField(1);
}

