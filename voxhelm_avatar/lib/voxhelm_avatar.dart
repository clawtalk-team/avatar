/// Voxhelm Avatar — SVG talking avatar with viseme-driven lip-sync.
///
/// Usage:
/// ```dart
/// import 'package:voxhelm_avatar/voxhelm_avatar.dart';
///
/// // Load SVGs
/// final visemeSet = await VisemeSet.fromAssetBundle(context, 'assets/heads/young_woman');
///
/// // Create controllers
/// final visemeCtrl = VisemeController();
/// final blinkCtrl = BlinkController()..start();
///
/// // Build widget
/// VoxhelmAvatar(
///   visemeSet: visemeSet,
///   controller: visemeCtrl,
///   blinkController: blinkCtrl,
///   size: 200,
/// )
///
/// // Drive from audio position
/// visemeCtrl.setTimeline(timeline);
/// visemeCtrl.tick(audioPositionSeconds);
/// ```
library voxhelm_avatar;

export 'src/animation_frame_controller.dart';
export 'src/animation_mode_controller.dart';
export 'src/avatar_widget.dart';
export 'src/viseme_controller.dart';
export 'src/blink_controller.dart';
export 'src/models/viseme_set.dart';
export 'src/models/phoneme_event.dart';
