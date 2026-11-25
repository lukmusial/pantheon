using UnrealBuildTool;

public class PantheonEditorTarget : TargetRules
{
	public PantheonEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("Pantheon");
	}
}
