// Free walk-through of the Pantheon (follow-up F2): a visitor who walks with collision or flies, and
// zooms the lens. Input is built in code (Enhanced Input objects created at start), so the project
// needs no input assets.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputActionValue.h"
#include "PantheonVisitor.generated.h"

class UCameraComponent;
class UInputAction;
class UInputMappingContext;

/** A place to jump to with Tab: position and look-at point, in metres in Blender axes (as the scripts). */
struct FPantheonViewpoint
{
	FString Name;
	FVector Position;
	FVector LookAt;
};

/** A camera set-up for -PantheonShots: position, look-at point (metres, Blender axes) and field of view. */
struct FPantheonShot
{
	FString Name;
	FVector Position;
	FVector LookAt;
	float Fov = 90.0f;
	float Wait = -1.0f;   // seconds before the screenshot; below 0: -PantheonShotWait
};

/** A camera key for -PantheonFilm: when, where, what it looks at, field of view and exposure (EV). */
struct FPantheonFilmKey
{
	float Time = 0.0f;
	FVector Position;   // Unreal cm
	FVector LookAt;
	float Fov = 75.0f;
	float EV = 5.0f;
};

UCLASS()
class PANTHEON_API APantheonVisitor : public ACharacter
{
	GENERATED_BODY()

public:
	APantheonVisitor();

	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;

	/** Blender metres (Z up, +Y towards the entrance) to Unreal centimetres (Y flipped). */
	static FVector ToUnreal(const FVector& BlenderMetres) { return FVector(BlenderMetres.X, -BlenderMetres.Y, BlenderMetres.Z) * 100.0; }
	static FVector ToBlender(const FVector& UnrealCm) { return FVector(UnrealCm.X, -UnrealCm.Y, UnrealCm.Z) / 100.0; }

	/** Spawn transform for the first viewpoint (the forecourt, facing the portico). */
	static FTransform StartTransform();

	// read by the HUD
	bool IsFlying() const;
	float GetZoom() const { return 90.0f / CurrentFov; }
	float GetExposure() const { return CurrentExposure; }
	bool IsFilming() const { return Film.Num() > 0; }
	float GetExposureOffset() const { return ExposureOffset; }
	const FString& GetViewpointName() const { return ViewpointName; }
	int32 GetQualityLevel() const { return QualityLevel; }
	bool bShowHelp = true;

protected:
	virtual void BeginPlay() override;

private:
	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY()
	TObjectPtr<UInputMappingContext> Mapping;

	UPROPERTY()
	TObjectPtr<UInputAction> MoveAction;
	UPROPERTY()
	TObjectPtr<UInputAction> LookAction;
	UPROPERTY()
	TObjectPtr<UInputAction> UpDownAction;
	UPROPERTY()
	TObjectPtr<UInputAction> JumpAction;
	UPROPERTY()
	TObjectPtr<UInputAction> SprintAction;
	UPROPERTY()
	TObjectPtr<UInputAction> FlyAction;
	UPROPERTY()
	TObjectPtr<UInputAction> ZoomAction;
	UPROPERTY()
	TObjectPtr<UInputAction> ZoomHoldAction;
	UPROPERTY()
	TObjectPtr<UInputAction> ResetAction;
	UPROPERTY()
	TObjectPtr<UInputAction> ExposureAction;
	UPROPERTY()
	TObjectPtr<UInputAction> ViewpointAction;
	UPROPERTY()
	TObjectPtr<UInputAction> HelpAction;
	UPROPERTY()
	TObjectPtr<UInputAction> GhostAction;
	UPROPERTY()
	TObjectPtr<UInputAction> QualityAction;
	UPROPERTY()
	TObjectPtr<UInputAction> QuitAction;

	void BuildInput();

	void Move(const FInputActionValue& Value);
	void Look(const FInputActionValue& Value);
	void UpDown(const FInputActionValue& Value);
	void SprintOn(const FInputActionValue& Value);
	void SprintOff(const FInputActionValue& Value);
	void ToggleFly(const FInputActionValue& Value);
	void Zoom(const FInputActionValue& Value);
	void ZoomHoldOn(const FInputActionValue& Value);
	void ZoomHoldOff(const FInputActionValue& Value);
	void ResetView(const FInputActionValue& Value);
	void NudgeExposure(const FInputActionValue& Value);
	void NextViewpoint(const FInputActionValue& Value);
	void ToggleHelp(const FInputActionValue& Value);
	void ToggleGhosts(const FInputActionValue& Value);
	void SetQuality(const FInputActionValue& Value);
	void Quit(const FInputActionValue& Value);

	void ApplySpeeds();
	void SetGhosts(bool bOn, float PrerollSeconds = 0.0f, float PriestPrerollSeconds = 0.0f);
	TWeakObjectPtr<AActor> Ghosts;   // the F3 ghost driver while ghosts are on
	void ApplyQuality(int32 Level);
	void GoTo(int32 Index);
	float TargetExposure() const;

	TArray<FPantheonViewpoint> Viewpoints;
	int32 ViewpointIndex = 0;
	FString ViewpointName;

	// -PantheonTour on the command line: visit every viewpoint, walk a little, log and screenshot, quit
	void TickTour(float DeltaSeconds);
	bool bTour = false;
	float TourTime = 0.0f;
	int32 TourStep = -1;
	bool bTourShot = false;
	int32 TourFrames = 0;
	float TourFrameTime = 0.0f;

	// -PantheonShots=<file> [-PantheonShotWait=<s>]: screenshots from listed camera set-ups, then quit
	void LoadShots(const FString& File);
	void TickShots(float DeltaSeconds);
	TArray<FPantheonShot> Shots;
	int32 ShotIndex = -1;
	float ShotTime = 0.0f;
	float ShotWait = 4.0f;
	float ShotStart = 0.0f;
	float ShotNext = 0.0f;
	bool bShotTaken = false;

	// -PantheonFilm=<file>: fly a scripted camera path and save every frame (see LoadFilm)
	void LoadFilm(const FString& File);
	void TickFilm();
	TArray<FPantheonFilmKey> Film;
	/** "follow" in a film: from T0 to T1 the camera stands behind a ghost, on the line from what the
	 * camera looks at through the ghost (so the ghost is in the foreground of its goal), Back metres
	 * behind it, Side to the right, Height above the floor; Ease seconds to get there and away. */
	struct FFilmFollow
	{
		float T0 = 0.0f, T1 = 0.0f;
		int32 Ghost = 0;
		float Back = 2.0f, Side = 0.6f, Height = 1.8f, Ease = 3.0f;
	};
	TArray<FFilmFollow> FilmFollows;
	float FilmPreroll = 0.0f;
	float FilmPriestPreroll = 0.0f;
	FVector FilmFollowEye = FVector::ZeroVector;
	bool bFilmFollowing = false;
	FString FilmOut;
	float FilmFps = 30.0f;
	float FilmSpeed = 1.0f;   // film seconds (the keys' and the ghosts' time) per second of the recording
	int32 FilmStep = 1;
	int32 FilmWarmFrames = 0;
	int32 FilmTick = -1;

	bool bStartViewSet = false;
	static constexpr float LookSettleSeconds = 1.0f;

	bool bHelpTimedOut = false;
	bool bSprint = false;
	bool bZoomHold = false;
	float TargetFov = 90.0f;     // set by the wheel
	float CurrentFov = 90.0f;
	float CurrentExposure = 1.5f;
	float ExposureOffset = 0.0f;
	int32 QualityLevel = 1;   // smooth
};
