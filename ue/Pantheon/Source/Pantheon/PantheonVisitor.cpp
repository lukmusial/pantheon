#include "PantheonVisitor.h"

#include "Camera/CameraComponent.h"
#include "F3GhostDriver.h"
#include "PantheonLeakTest.h"
#include "Components/CapsuleComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameUserSettings.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace
{
	// Blender metres: the entrance is on +Y, the apse (Jupiter) on -Y
	constexpr float RotundaRadius = 21.72f;   // inner face of the drum
	constexpr float PorticoRear = 33.4f;      // portico rear wall; the door passage runs from here to the drum
	constexpr float DoorPassageHalfWidth = 3.8f;   // the passage through the portico's block (door_hw + 0.75)
	constexpr float DrumOuterRadius = 27.92f;      // outer face of the drum; the lanes beside it are outside
	const FVector2D JupiterXY(0.0f, -22.5f);

	// camera exposure compensation (EV), as in the films: daylight outside, interior, the sunlit Jupiter
	constexpr float OutsideEV = 2.0f;   // 1.5 until the sun went from 4.5 to 3.0 lux (2026-11-23)
	constexpr float InsideEV = 5.0f;
	constexpr float JupiterEV = 3.0f;

	constexpr float EyeAboveCapsuleCentre = 64.0f;   // cm; capsule half height 88, so the eye is at 1.52 m
	constexpr float HelpSeconds = 25.0f;

	TArray<FPantheonViewpoint> MakeViewpoints()
	{
		return {
			// on the forecourt's paving, 1.4 below the portico floor (eye 1.6 above it), looking in
			{TEXT("Forecourt"), FVector(0.0, 60.0, 0.2), FVector(0.0, 24.0, 4.5)},
			{TEXT("Portico"), FVector(-3.0, 41.0, 1.6), FVector(0.0, 20.0, 5.0)},
			{TEXT("Bronze doors"), FVector(0.0, 24.0, 1.6), FVector(0.0, 0.0, 6.0)},
			{TEXT("Under the oculus"), FVector(0.0, 0.5, 1.6), FVector(0.0, -2.0, 40.0)},
			{TEXT("Minerva"), FVector(-13.1, -13.1, 1.6), FVector(-16.95, -16.95, 2.6)},
			{TEXT("Ceres"), FVector(-15.7, -6.5, 1.6), FVector(-19.56, -8.1, 3.4)},
			{TEXT("Jupiter"), FVector(0.0, -11.5, 1.6), FVector(0.0, -22.5, 6.0)},
			{TEXT("Attic (flying)"), FVector(8.0, -4.0, 11.0), FVector(20.0, -9.0, 17.0)},
			{TEXT("Dome (flying)"), FVector(0.0, 12.0, 24.0), FVector(0.0, -10.0, 34.0)},
		};
	}

	UInputAction* NewAction(UObject* Outer, EInputActionValueType Type)
	{
		UInputAction* Action = NewObject<UInputAction>(Outer);
		Action->ValueType = Type;
		return Action;
	}

	template <typename T>
	T* AddModifier(UObject* Outer, FEnhancedActionKeyMapping& Mapping)
	{
		T* Modifier = NewObject<T>(Outer);
		Mapping.Modifiers.Add(Modifier);
		return Modifier;
	}
}

APantheonVisitor::APantheonVisitor()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(30.0f, 88.0f);
	BaseEyeHeight = EyeAboveCapsuleCentre;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(GetCapsuleComponent());
	Camera->SetRelativeLocation(FVector(0.0, 0.0, EyeAboveCapsuleCentre));
	Camera->bUsePawnControlRotation = true;
	Camera->SetFieldOfView(90.0f);

	// The film look: manual exposure (the level's post-process volume is manual too), keyed by place
	// in Tick; less motion blur than the film, since the viewer turns the camera by hand.
	FPostProcessSettings& PP = Camera->PostProcessSettings;
	PP.bOverride_AutoExposureMethod = true;
	PP.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
	PP.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
	PP.AutoExposureApplyPhysicalCameraExposure = false;
	PP.bOverride_AutoExposureBias = true;
	PP.AutoExposureBias = OutsideEV;
	PP.bOverride_MotionBlurAmount = true;
	PP.MotionBlurAmount = 0.2f;
	Camera->PostProcessBlendWeight = 1.0f;

	bUseControllerRotationYaw = true;
	bUseControllerRotationPitch = false;
	bUseControllerRotationRoll = false;

	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->MaxStepHeight = 45.0f;
	Move->BrakingDecelerationWalking = 1200.0f;
	Move->BrakingDecelerationFlying = 1500.0f;
	Move->JumpZVelocity = 380.0f;
	Move->AirControl = 0.3f;

	Viewpoints = MakeViewpoints();
	ViewpointName = Viewpoints[0].Name;
	ApplySpeeds();
}

FTransform APantheonVisitor::StartTransform()
{
	const FPantheonViewpoint V = MakeViewpoints()[0];
	const FVector Eye = ToUnreal(V.Position);
	const FRotator Rot = (ToUnreal(V.LookAt) - Eye).Rotation();
	return FTransform(FRotator(0.0, Rot.Yaw, 0.0), Eye - FVector(0.0, 0.0, EyeAboveCapsuleCentre));
}

void APantheonVisitor::BeginPlay()
{
	Super::BeginPlay();
	bTour = FParse::Param(FCommandLine::Get(), TEXT("PantheonTour"));
	// -PantheonQuality=1|2|3 starts at that quality (the tour uses it to compare settings)
	int32 Quality = QualityLevel;
	if (FParse::Value(FCommandLine::Get(), TEXT("PantheonQuality="), Quality))
	{
		QualityLevel = FMath::Clamp(Quality, 1, 3);
	}
	ApplyQuality(QualityLevel);
	CurrentExposure = TargetExposure();
	if (FParse::Param(FCommandLine::Get(), TEXT("PantheonGhosts")))
	{
		SetGhosts(true);
	}
	FString ShotsFile;
	if (FParse::Value(FCommandLine::Get(), TEXT("PantheonShots="), ShotsFile))
	{
		LoadShots(ShotsFile);
	}
	FString FilmFile;
	if (FParse::Value(FCommandLine::Get(), TEXT("PantheonFilm="), FilmFile))
	{
		LoadFilm(FilmFile);
	}
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		const FPantheonViewpoint& V = Viewpoints[0];
		PC->SetControlRotation((ToUnreal(V.LookAt) - ToUnreal(V.Position)).Rotation());
	}
	// -PantheonLeakTest=<file>: look for holes in the walls with this capsule, write them out, quit
	FString LeakFile;
	if (FParse::Value(FCommandLine::Get(), TEXT("PantheonLeakTest="), LeakFile))
	{
		RunPantheonLeakTest(GetWorld(), GetCapsuleComponent()->GetUnscaledCapsuleRadius(),
			GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight(), LeakFile);
		FPlatformMisc::RequestExit(false);
	}
}

void APantheonVisitor::BuildInput()
{
	if (Mapping)
	{
		return;
	}
	Mapping = NewObject<UInputMappingContext>(this);

	MoveAction = NewAction(this, EInputActionValueType::Axis2D);
	// X right, Y forward
	Mapping->MapKey(MoveAction, EKeys::D);
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(MoveAction, EKeys::A));
	AddModifier<UInputModifierSwizzleAxis>(this, Mapping->MapKey(MoveAction, EKeys::W));
	{
		FEnhancedActionKeyMapping& S = Mapping->MapKey(MoveAction, EKeys::S);
		AddModifier<UInputModifierSwizzleAxis>(this, S);
		AddModifier<UInputModifierNegate>(this, S);
	}
	Mapping->MapKey(MoveAction, EKeys::Right);
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(MoveAction, EKeys::Left));
	AddModifier<UInputModifierSwizzleAxis>(this, Mapping->MapKey(MoveAction, EKeys::Up));
	{
		FEnhancedActionKeyMapping& S = Mapping->MapKey(MoveAction, EKeys::Down);
		AddModifier<UInputModifierSwizzleAxis>(this, S);
		AddModifier<UInputModifierNegate>(this, S);
	}
	AddModifier<UInputModifierDeadZone>(this, Mapping->MapKey(MoveAction, EKeys::Gamepad_Left2D));

	LookAction = NewAction(this, EInputActionValueType::Axis2D);
	Mapping->MapKey(LookAction, EKeys::Mouse2D);
	{
		FEnhancedActionKeyMapping& Pad = Mapping->MapKey(LookAction, EKeys::Gamepad_Right2D);
		AddModifier<UInputModifierDeadZone>(this, Pad);
		UInputModifierScalar* Scale = AddModifier<UInputModifierScalar>(this, Pad);
		Scale->Scalar = FVector(4.0, 4.0, 1.0);
	}

	UpDownAction = NewAction(this, EInputActionValueType::Axis1D);
	Mapping->MapKey(UpDownAction, EKeys::E);
	Mapping->MapKey(UpDownAction, EKeys::SpaceBar);
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(UpDownAction, EKeys::Q));
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(UpDownAction, EKeys::C));

	JumpAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(JumpAction, EKeys::SpaceBar);
	Mapping->MapKey(JumpAction, EKeys::Gamepad_FaceButton_Bottom);

	SprintAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(SprintAction, EKeys::LeftShift);
	Mapping->MapKey(SprintAction, EKeys::Gamepad_LeftThumbstick);

	FlyAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(FlyAction, EKeys::F);
	Mapping->MapKey(FlyAction, EKeys::Gamepad_FaceButton_Top);

	ZoomAction = NewAction(this, EInputActionValueType::Axis1D);
	Mapping->MapKey(ZoomAction, EKeys::MouseWheelAxis);
	Mapping->MapKey(ZoomAction, EKeys::Equals);
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(ZoomAction, EKeys::Hyphen));
	Mapping->MapKey(ZoomAction, EKeys::Gamepad_RightTriggerAxis);
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(ZoomAction, EKeys::Gamepad_LeftTriggerAxis));

	ZoomHoldAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(ZoomHoldAction, EKeys::RightMouseButton);
	Mapping->MapKey(ZoomHoldAction, EKeys::Z);

	ResetAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(ResetAction, EKeys::R);

	ExposureAction = NewAction(this, EInputActionValueType::Axis1D);
	Mapping->MapKey(ExposureAction, EKeys::RightBracket);
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(ExposureAction, EKeys::LeftBracket));

	ViewpointAction = NewAction(this, EInputActionValueType::Axis1D);
	Mapping->MapKey(ViewpointAction, EKeys::Tab);
	Mapping->MapKey(ViewpointAction, EKeys::Gamepad_RightShoulder);
	AddModifier<UInputModifierNegate>(this, Mapping->MapKey(ViewpointAction, EKeys::Gamepad_LeftShoulder));

	GhostAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(GhostAction, EKeys::G);
	HelpAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(HelpAction, EKeys::H);
	Mapping->MapKey(HelpAction, EKeys::F1);

	QualityAction = NewAction(this, EInputActionValueType::Axis1D);
	Mapping->MapKey(QualityAction, EKeys::One);
	AddModifier<UInputModifierScalar>(this, Mapping->MapKey(QualityAction, EKeys::Two))->Scalar = FVector(2.0, 1.0, 1.0);
	AddModifier<UInputModifierScalar>(this, Mapping->MapKey(QualityAction, EKeys::Three))->Scalar = FVector(3.0, 1.0, 1.0);

	QuitAction = NewAction(this, EInputActionValueType::Boolean);
	Mapping->MapKey(QuitAction, EKeys::Escape);
	Mapping->MapKey(QuitAction, EKeys::Gamepad_Special_Right);
}

void APantheonVisitor::PawnClientRestart()
{
	BuildInput();
	Super::PawnClientRestart();
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Input = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Input->ClearAllMappings();
			Input->AddMappingContext(Mapping, 0);
		}
		// BeginPlay runs before the controller possesses the pawn, so the start view is set here too
		if (!bStartViewSet)
		{
			const FPantheonViewpoint& V = Viewpoints[0];
			PC->SetControlRotation((ToUnreal(V.LookAt) - ToUnreal(V.Position)).Rotation());
			bStartViewSet = true;
		}
	}
}

void APantheonVisitor::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	BuildInput();
	UEnhancedInputComponent* In = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!In)
	{
		UE_LOG(LogTemp, Error, TEXT("Pantheon: the input component is not an EnhancedInputComponent; check DefaultInput.ini"));
		return;
	}
	In->BindAction(MoveAction, ETriggerEvent::Triggered, this, &APantheonVisitor::Move);
	In->BindAction(LookAction, ETriggerEvent::Triggered, this, &APantheonVisitor::Look);
	In->BindAction(UpDownAction, ETriggerEvent::Triggered, this, &APantheonVisitor::UpDown);
	In->BindAction(JumpAction, ETriggerEvent::Started, this, &ACharacter::Jump);
	In->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
	In->BindAction(SprintAction, ETriggerEvent::Started, this, &APantheonVisitor::SprintOn);
	In->BindAction(SprintAction, ETriggerEvent::Completed, this, &APantheonVisitor::SprintOff);
	In->BindAction(FlyAction, ETriggerEvent::Started, this, &APantheonVisitor::ToggleFly);
	In->BindAction(ZoomAction, ETriggerEvent::Triggered, this, &APantheonVisitor::Zoom);
	In->BindAction(ZoomHoldAction, ETriggerEvent::Started, this, &APantheonVisitor::ZoomHoldOn);
	In->BindAction(ZoomHoldAction, ETriggerEvent::Completed, this, &APantheonVisitor::ZoomHoldOff);
	In->BindAction(ResetAction, ETriggerEvent::Started, this, &APantheonVisitor::ResetView);
	In->BindAction(ExposureAction, ETriggerEvent::Started, this, &APantheonVisitor::NudgeExposure);
	In->BindAction(ViewpointAction, ETriggerEvent::Started, this, &APantheonVisitor::NextViewpoint);
	In->BindAction(HelpAction, ETriggerEvent::Started, this, &APantheonVisitor::ToggleHelp);
	In->BindAction(GhostAction, ETriggerEvent::Started, this, &APantheonVisitor::ToggleGhosts);
	In->BindAction(QualityAction, ETriggerEvent::Started, this, &APantheonVisitor::SetQuality);
	In->BindAction(QuitAction, ETriggerEvent::Started, this, &APantheonVisitor::Quit);
}

bool APantheonVisitor::IsFlying() const
{
	return GetCharacterMovement()->MovementMode == MOVE_Flying;
}

void APantheonVisitor::Move(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	if (!Controller)
	{
		return;
	}
	const FRotator View = Controller->GetControlRotation();
	// flying goes where the camera looks; walking stays level
	const FRotator Basis = IsFlying() ? View : FRotator(0.0, View.Yaw, 0.0);
	const FRotationMatrix M(Basis);
	AddMovementInput(M.GetUnitAxis(EAxis::X), Axis.Y);
	AddMovementInput(M.GetUnitAxis(EAxis::Y), Axis.X);
}

void APantheonVisitor::Look(const FInputActionValue& Value)
{
	// slower turning when zoomed in, so a distant detail stays easy to hold
	// the first moments after start bring a large mouse delta from the cursor being captured, which
	// threw the start view at the ground: ignore look input until the view is settled
	if (GetWorld()->GetTimeSeconds() < LookSettleSeconds)
	{
		return;
	}
	const FVector2D Axis = Value.Get<FVector2D>() * (CurrentFov / 90.0f);
	AddControllerYawInput(Axis.X);
	AddControllerPitchInput(-Axis.Y);
}

void APantheonVisitor::UpDown(const FInputActionValue& Value)
{
	if (IsFlying())
	{
		AddMovementInput(FVector::UpVector, Value.Get<float>());
	}
}

void APantheonVisitor::SprintOn(const FInputActionValue&)
{
	bSprint = true;
	ApplySpeeds();
}

void APantheonVisitor::SprintOff(const FInputActionValue&)
{
	bSprint = false;
	ApplySpeeds();
}

void APantheonVisitor::ApplySpeeds()
{
	UCharacterMovementComponent* Move = GetCharacterMovement();
	// The stroll: 20 % above the first build's (user, 2026-11-23), then 30 % more (user, 2026-11-25)
	Move->MaxWalkSpeed = bSprint ? 625.0f : 299.0f;      // a stroll, or a brisk walk
	Move->MaxFlySpeed = bSprint ? 2160.0f : 720.0f;
	Move->MaxAcceleration = bSprint ? 2900.0f : 1450.0f;
}

void APantheonVisitor::ToggleFly(const FInputActionValue&)
{
	GetCharacterMovement()->SetMovementMode(IsFlying() ? MOVE_Falling : MOVE_Flying);
}

void APantheonVisitor::Zoom(const FInputActionValue& Value)
{
	// one wheel notch is about 13 %; 90 degrees (1x) down to 6 degrees (15x)
	TargetFov = FMath::Clamp(TargetFov * FMath::Pow(0.87f, Value.Get<float>()), 6.0f, 90.0f);
}

void APantheonVisitor::ZoomHoldOn(const FInputActionValue&)
{
	bZoomHold = true;
}

void APantheonVisitor::ZoomHoldOff(const FInputActionValue&)
{
	bZoomHold = false;
}

void APantheonVisitor::ResetView(const FInputActionValue&)
{
	TargetFov = 90.0f;
	ExposureOffset = 0.0f;
}

void APantheonVisitor::NudgeExposure(const FInputActionValue& Value)
{
	ExposureOffset = FMath::Clamp(ExposureOffset + 0.5f * FMath::Sign(Value.Get<float>()), -4.0f, 4.0f);
}

void APantheonVisitor::NextViewpoint(const FInputActionValue& Value)
{
	const int32 Step = Value.Get<float>() < 0.0f ? -1 : 1;
	GoTo((ViewpointIndex + Step + Viewpoints.Num()) % Viewpoints.Num());
}

void APantheonVisitor::GoTo(int32 Index)
{
	ViewpointIndex = Index;
	const FPantheonViewpoint& V = Viewpoints[Index];
	ViewpointName = V.Name;
	const FVector Eye = ToUnreal(V.Position);
	// raised viewpoints (attic, dome) are seen flying; the rest walking
	GetCharacterMovement()->SetMovementMode(V.Position.Z > 3.0 ? MOVE_Flying : MOVE_Falling);
	GetCharacterMovement()->StopMovementImmediately();
	SetActorLocation(Eye - FVector(0.0, 0.0, EyeAboveCapsuleCentre), false, nullptr, ETeleportType::TeleportPhysics);
	if (Controller)
	{
		Controller->SetControlRotation((ToUnreal(V.LookAt) - Eye).Rotation());
	}
	CurrentExposure = TargetExposure();
}

void APantheonVisitor::ToggleGhosts(const FInputActionValue&)
{
	SetGhosts(!Ghosts.IsValid());
}

void APantheonVisitor::SetGhosts(bool bOn, float PrerollSeconds, float PriestPrerollSeconds)
{
	// F3: invisible figures walking through low fog, seen only as the shapes they cut into it
	if (!bOn)
	{
		if (Ghosts.IsValid())
		{
			Ghosts->Destroy();
		}
		Ghosts.Reset();
		return;
	}
	if (Ghosts.IsValid())
	{
		return;
	}
	AF3GhostDriver* D = GetWorld()->SpawnActorDeferred<AF3GhostDriver>(AF3GhostDriver::StaticClass(), FTransform::Identity);
	D->bSpawnScene = true;
	D->PrerollSeconds = PrerollSeconds;
	D->PriestPrerollSeconds = PriestPrerollSeconds;
	D->FinishSpawning(FTransform::Identity);
	Ghosts = D;
}

void APantheonVisitor::ToggleHelp(const FInputActionValue&)
{
	bShowHelp = !bShowHelp;
	bHelpTimedOut = true;   // once toggled by hand, the timer no longer hides it
}

void APantheonVisitor::SetQuality(const FInputActionValue& Value)
{
	ApplyQuality(FMath::Clamp(FMath::RoundToInt(Value.Get<float>()), 1, 3));
}

void APantheonVisitor::ApplyQuality(int32 Level)
{
	// 1 smooth, 2 balanced, 3 detailed: scalability and internal resolution, which temporal super
	// resolution brings back up to the window size. Measured inside the rotunda at 3440x1440 on an M5 Pro
	// (-PantheonTour): high at 50 % about 50 fps, high at 67 % about 33, epic at 67 % about 21;
	// cinematic at 100 % ran at 5 fps for a barely visible gain (crisper coffer shading), so it is not offered.
	QualityLevel = Level;
	static const int32 Scalability[] = {2, 2, 3};
	static const float ScreenPercentage[] = {50.0f, 67.0f, 67.0f};
	if (UGameUserSettings* Settings = UGameUserSettings::GetGameUserSettings())
	{
		Settings->SetOverallScalabilityLevel(Scalability[Level - 1]);
		// quality only: ApplySettings would also re-apply the saved window mode. After an offscreen
		// self-test saved "windowed fullscreen", a windowed launch hung on a black window waiting for
		// the macOS fullscreen transition at start (user, 2026-11-23)
		Settings->ApplyNonResolutionSettings();
	}
	if (IConsoleVariable* SP = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage")))
	{
		SP->Set(ScreenPercentage[Level - 1], ECVF_SetByCode);
	}
	// The oculus shaft is volumetric fog: at the scalability default (16 px froxels, 64 depth slices)
	// the rosettes' shadows and the shaft edge came out as blocks. Finer froxels at every level, plus
	// more depth slices and stronger temporal smoothing; set after the scalability level, which would
	// otherwise reset them.
	// 4-5 px froxels (user, 2026-11-23: still jagged seen from under the oculus at 8 px); the grid
	// stays under the size that overflowed in the films (4 px x 256 slices at full 1080p) even at
	// 3440x1440, since the grid follows the internal resolution (50 % / 67 %)
	static const int32 FogPixels[] = {4, 5, 5};
	static const int32 FogSlices[] = {160, 192, 192};
	auto SetCVar = [](const TCHAR* Name, float V)
	{
		if (IConsoleVariable* C = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			C->Set(V, ECVF_SetByCode);
		}
	};
	SetCVar(TEXT("r.VolumetricFog.GridPixelSize"), FogPixels[Level - 1]);
	SetCVar(TEXT("r.VolumetricFog.GridSizeZ"), FogSlices[Level - 1]);
	SetCVar(TEXT("r.VolumetricFog.TemporalReprojection"), 1);
	SetCVar(TEXT("r.VolumetricFog.HistoryWeight"), 0.95f);
	SetCVar(TEXT("r.VolumetricFog.Jitter"), 1);
	// Lumen: denser screen probes and longer accumulation. The half domes over the entrance and the
	// apse are lit only by bounced light and shimmered (user, 2026-11-23); this cut the measured
	// shimmer on the entrance vault by about a quarter at no measurable frame cost.
	SetCVar(TEXT("r.Lumen.ScreenProbeGather.TracingOctahedronResolution"), 16);
	// One screen probe per 12/10/8 pixels instead of 16. Seen wide, the bounce light in the
	// entrance vault was interpolated across probes too far apart and showed as a blocky,
	// shifting mass that zooming in smoothed out (user, 2026-11-23). Costs about a quarter of the
	// frame rate on "smooth" (inside about 55-79 fps at 1920x1080).
	static const int32 ProbeSpacing[] = {12, 10, 8};
	SetCVar(TEXT("r.Lumen.ScreenProbeGather.DownsampleFactor"), ProbeSpacing[Level - 1]);
	SetCVar(TEXT("r.Lumen.ScreenProbeGather.Temporal.MaxFramesAccumulated"), 32);
	// Sun shadows are ray traced (APantheonGameMode::BeginPlay); the fire lights keep virtual shadow maps.
	SetCVar(TEXT("r.Shadow.Virtual.Enable"), 1);
	// The fires' soft shadows: finer pages, more rays and more dither. At the defaults the shadow of a
	// candelabrum's shaft on the side of Jupiter's pedestal came out as a column of jagged triangles,
	// the shadow map's texels drawn large (user, 2026-11-24)
	static const float LocalLodBias[] = {0.0f, -0.5f, -1.0f};
	static const int32 LocalRays[] = {8, 12, 16};
	static const int32 LocalSamples[] = {4, 6, 8};
	SetCVar(TEXT("r.Shadow.Virtual.ResolutionLodBiasLocal"), LocalLodBias[Level - 1]);
	SetCVar(TEXT("r.Shadow.Virtual.SMRT.RayCountLocal"), LocalRays[Level - 1]);
	SetCVar(TEXT("r.Shadow.Virtual.SMRT.SamplesPerRayLocal"), LocalSamples[Level - 1]);
	SetCVar(TEXT("r.Shadow.Virtual.SMRT.TexelDitherScaleLocal"), 4.0f);
}

void APantheonVisitor::Quit(const FInputActionValue&)
{
	UKismetSystemLibrary::QuitGame(this, Cast<APlayerController>(GetController()), EQuitPreference::Quit, false);
}

float APantheonVisitor::TargetExposure() const
{
	const FVector P = ToBlender(GetActorLocation());
	// 0 outside (portico, forecourt, the lanes beside the drum), 1 inside the drum and its recesses
	// (they reach into the wall, beyond RotundaRadius), a ramp through the door passage
	float Inside = 0.0f;
	if (FMath::Abs(P.X) < DoorPassageHalfWidth && P.Y > 0.0f)
	{
		Inside = FMath::Clamp((PorticoRear - P.Y) / (PorticoRear - RotundaRadius), 0.0f, 1.0f);
	}
	else if (FVector2D(P.X, P.Y).Size() < DrumOuterRadius)
	{
		Inside = 1.0f;
	}
	float EV = FMath::Lerp(OutsideEV, InsideEV, Inside);
	// near the sunlit Jupiter his paint clips at the interior exposure
	const float Near = FMath::Clamp((10.0f - FVector2D::Distance(FVector2D(P.X, P.Y), JupiterXY)) / 4.0f, 0.0f, 1.0f);
	EV = FMath::Lerp(EV, JupiterEV, Near * Inside);
	return EV + ExposureOffset;
}

void APantheonVisitor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const float WantFov = bZoomHold ? FMath::Min(TargetFov, 22.0f) : TargetFov;
	CurrentFov = FMath::FInterpTo(CurrentFov, WantFov, DeltaSeconds, 8.0f);
	Camera->SetFieldOfView(CurrentFov);

	// the eye adapts over a second or two, as when walking in from the sunlit portico
	CurrentExposure = FMath::FInterpTo(CurrentExposure, TargetExposure(), DeltaSeconds, 1.2f);
	Camera->PostProcessSettings.AutoExposureBias = CurrentExposure;

	if (!bHelpTimedOut && GetWorld()->GetTimeSeconds() > HelpSeconds)
	{
		bHelpTimedOut = true;
		bShowHelp = false;   // H brings it back
	}

	// hold the start view until look input is accepted (see Look)
	if (bStartViewSet && !bTour && Shots.Num() == 0 && Film.Num() == 0 && ViewpointIndex == 0 && Controller
		&& GetWorld()->GetTimeSeconds() < LookSettleSeconds)
	{
		const FPantheonViewpoint& V = Viewpoints[0];
		Controller->SetControlRotation((ToUnreal(V.LookAt) - ToUnreal(V.Position)).Rotation());
	}

	if (bTour)
	{
		TickTour(DeltaSeconds);
	}
	if (Shots.Num() > 0)
	{
		TickShots(DeltaSeconds);
	}
	if (Film.Num() > 0)
	{
		TickFilm();
	}

	// fell off the edge of the ground (it ends 150 m out): back to the start
	if (GetActorLocation().Z < -2000.0)
	{
		GoTo(0);
	}
}

void APantheonVisitor::TickTour(float DeltaSeconds)
{
	constexpr float StepSeconds = 7.0f;
	TourTime += DeltaSeconds;
	const int32 Step = FMath::FloorToInt(TourTime / StepSeconds);
	const float InStep = TourTime - Step * StepSeconds;
	if (Step >= Viewpoints.Num())
	{
		UE_LOG(LogTemp, Display, TEXT("PantheonTour: done"));
		UKismetSystemLibrary::QuitGame(this, Cast<APlayerController>(GetController()), EQuitPreference::Quit, false);
		bTour = false;
		return;
	}
	if (Step != TourStep)
	{
		TourStep = Step;
		bTourShot = false;
		TourFrames = 0;
		TourFrameTime = 0.0f;
		GoTo(Step);
		bShowHelp = false;
		bHelpTimedOut = true;
	}
	// walk (or fly) forward for two seconds: checks the floor holds and walls stop the visitor
	if (InStep > 2.0f && InStep < 4.0f && Controller)
	{
		const FRotator View = Controller->GetControlRotation();
		AddMovementInput(FRotationMatrix(IsFlying() ? View : FRotator(0.0, View.Yaw, 0.0)).GetUnitAxis(EAxis::X), 1.0f);
	}
	if (InStep > 4.0f && InStep <= 6.0f)
	{
		TourFrameTime += DeltaSeconds;
		++TourFrames;
	}
	if (!bTourShot && InStep > 6.0f)
	{
		bTourShot = true;
		const FVector P = ToBlender(GetActorLocation());
		// Shipping builds write no log, so the tour also writes its own file beside the screenshots
		const FString Line = FString::Printf(TEXT("%d %s at (%.2f, %.2f, %.2f) m, %s, exposure %.2f, %.1f fps (mean over %d frames)"),
			Step, *ViewpointName, P.X, P.Y, P.Z, IsFlying() ? TEXT("flying") : TEXT("walking"), CurrentExposure,
			TourFrames / FMath::Max(TourFrameTime, 1e-4f), TourFrames);
		UE_LOG(LogTemp, Display, TEXT("PantheonTour: %s"), *Line);
		FFileHelper::SaveStringToFile(Line + TEXT("\n"), *(FPaths::ProjectSavedDir() / TEXT("Tour/tour.txt")),
			FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_Append);
		FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Tour/viewpoint_%02d.png"), Step), true, false);
	}
}

void APantheonVisitor::LoadShots(const FString& File)
{
	// one shot a line: name  x y z  look-x look-y look-z  [fov [wait-seconds]]   (metres, Blender axes;
	// # comments). A short wait after a shot at the same place gives a burst of frames, to measure flicker.
	TArray<FString> Lines;
	if (!FFileHelper::LoadFileToStringArray(Lines, *File))
	{
		UE_LOG(LogTemp, Error, TEXT("PantheonShots: cannot read %s"), *File);
		return;
	}
	for (const FString& Raw : Lines)
	{
		const FString Line = Raw.TrimStartAndEnd();
		if (Line.IsEmpty() || Line.StartsWith(TEXT("#")))
		{
			continue;
		}
		TArray<FString> F;
		Line.ParseIntoArrayWS(F);
		if (F.Num() < 7)
		{
			continue;
		}
		FPantheonShot S;
		S.Name = F[0];
		S.Position = FVector(FCString::Atod(*F[1]), FCString::Atod(*F[2]), FCString::Atod(*F[3]));
		S.LookAt = FVector(FCString::Atod(*F[4]), FCString::Atod(*F[5]), FCString::Atod(*F[6]));
		S.Fov = F.Num() > 7 ? FCString::Atof(*F[7]) : 90.0f;
		S.Wait = F.Num() > 8 ? FCString::Atof(*F[8]) : -1.0f;
		Shots.Add(S);
	}
	FParse::Value(FCommandLine::Get(), TEXT("PantheonShotWait="), ShotWait);
	bShowHelp = false;
	bHelpTimedOut = true;
	UE_LOG(LogTemp, Display, TEXT("PantheonShots: %d shots from %s"), Shots.Num(), *File);
}

void APantheonVisitor::TickShots(float DeltaSeconds)
{
	// -PantheonShots=<file>: fly to each shot, let Lumen and the fog history settle, screenshot, quit
	ShotTime += DeltaSeconds;
	if (ShotIndex < 0 || (bShotTaken && ShotTime >= ShotNext))
	{
		++ShotIndex;
		if (ShotIndex >= Shots.Num())
		{
			UE_LOG(LogTemp, Display, TEXT("PantheonShots: done"));
			Shots.Empty();
			UKismetSystemLibrary::QuitGame(this, Cast<APlayerController>(GetController()), EQuitPreference::Quit, false);
			return;
		}
		const FPantheonShot& S = Shots[ShotIndex];
		bShotTaken = false;
		ShotStart = ShotTime;
		// a burst at the same place stays put: a teleport cuts the camera and resets the temporal
		// history (anti-aliasing, Lumen, fog), which would show as flicker that is not there
		const bool bSamePlace = ShotIndex > 0 && Shots[ShotIndex - 1].Position.Equals(S.Position)
			&& Shots[ShotIndex - 1].LookAt.Equals(S.LookAt) && Shots[ShotIndex - 1].Fov == S.Fov;
		if (bSamePlace)
		{
			return;
		}
		const FVector Eye = ToUnreal(S.Position);
		GetCharacterMovement()->SetMovementMode(MOVE_Flying);
		GetCharacterMovement()->StopMovementImmediately();
		SetActorEnableCollision(false);
		SetActorLocation(Eye - FVector(0.0, 0.0, EyeAboveCapsuleCentre), false, nullptr, ETeleportType::TeleportPhysics);
		TargetFov = CurrentFov = S.Fov;
		Camera->SetFieldOfView(S.Fov);
		CurrentExposure = TargetExposure();
	}
	const FPantheonShot& S = Shots[ShotIndex];
	if (Controller)
	{
		Controller->SetControlRotation((ToUnreal(S.LookAt) - ToUnreal(S.Position)).Rotation());
	}
	const float Wait = S.Wait >= 0.0f ? S.Wait : ShotWait;
	if (!bShotTaken && ShotTime - ShotStart >= Wait)
	{
		bShotTaken = true;
		ShotNext = ShotTime + (S.Wait >= 0.0f ? 0.0f : 0.5f);
		FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Shots/%s.png"), *S.Name), false, false);
	}
}

void APantheonVisitor::LoadFilm(const FString& File)
{
	// -PantheonFilm=<file>: a film recorded from the game itself (user, 2026-11-23: not the full
	// render but the regular game engine). The file lists camera keys, one a line:
	//     seconds  x y z  look-x look-y look-z  fov  exposure      (metres, Blender axes; # comments)
	// The camera flies a smooth curve through them and every frame is saved as a screenshot. Game time
	// advances by exactly one film frame per rendered frame (fixed time step), so the film runs at
	// its own speed however long a frame takes, and the ghosts, which start with the film, are in
	// the same places on every run.
	//   -PantheonFilmOut=<folder>  where the frames go (default Saved/Film)
	//   -PantheonFilmFps=<n>       film frames per second (default 30)
	//   -PantheonFilmWarm=<s>      seconds held on the first key before the film starts, for the
	//                              lighting to settle (default 6)
	//   -PantheonFilmStep=<n>      save only every n-th frame (a quick preview of the path)
	//   -PantheonFilmSpeed=<x>     the whole film that many times faster (user, 2026-11-24: 30 % faster):
	//                              game time advances by x film frames per recorded frame, so camera,
	//                              ghosts and fires all speed up together and the motion stays even
	//                              (no frames are dropped)
	// Two more kinds of line:
	//     preroll <seconds>      the ghosts have been about that long when the film starts
	//     priest <seconds>       and the priest that much longer (to choose the moment of his prayer)
	//     follow <from> <to> <ghost> <back> <side> <height> [ease]
	//                            between those times the camera stands behind that ghost (0-3 the
	//                            worshippers, 4 the priest) as seen from what the keys look at: back
	//                            metres behind it, side to the right, height above the floor, so the
	//                            ghost is in the foreground of where it is going. The keys still give
	//                            what the camera looks at, the field of view and the exposure; ease
	//                            (default 3 s) is the time to move there from the keys' path and back.
	TArray<FString> Lines;
	if (!FFileHelper::LoadFileToStringArray(Lines, *File))
	{
		UE_LOG(LogTemp, Error, TEXT("PantheonFilm: cannot read %s"), *File);
		return;
	}
	for (const FString& Raw : Lines)
	{
		const FString Line = Raw.TrimStartAndEnd();
		if (Line.IsEmpty() || Line.StartsWith(TEXT("#")))
		{
			continue;
		}
		TArray<FString> F;
		Line.ParseIntoArrayWS(F);
		if (F[0] == TEXT("preroll") && F.Num() >= 2)
		{
			FilmPreroll = FCString::Atof(*F[1]);
			continue;
		}
		if (F[0] == TEXT("priest") && F.Num() >= 2)
		{
			FilmPriestPreroll = FCString::Atof(*F[1]);
			continue;
		}
		if (F[0] == TEXT("follow") && F.Num() >= 7)
		{
			FFilmFollow W;
			W.T0 = FCString::Atof(*F[1]);
			W.T1 = FCString::Atof(*F[2]);
			W.Ghost = FCString::Atoi(*F[3]);
			W.Back = FCString::Atof(*F[4]);
			W.Side = FCString::Atof(*F[5]);
			W.Height = FCString::Atof(*F[6]);
			W.Ease = F.Num() > 7 ? FMath::Max(FCString::Atof(*F[7]), 0.1f) : 3.0f;
			FilmFollows.Add(W);
			continue;
		}
		if (F.Num() < 9)
		{
			continue;
		}
		FPantheonFilmKey K;
		K.Time = FCString::Atof(*F[0]);
		K.Position = ToUnreal(FVector(FCString::Atod(*F[1]), FCString::Atod(*F[2]), FCString::Atod(*F[3])));
		K.LookAt = ToUnreal(FVector(FCString::Atod(*F[4]), FCString::Atod(*F[5]), FCString::Atod(*F[6])));
		K.Fov = FCString::Atof(*F[7]);
		K.EV = FCString::Atof(*F[8]);
		Film.Add(K);
	}
	if (Film.Num() < 2)
	{
		UE_LOG(LogTemp, Error, TEXT("PantheonFilm: %s has fewer than two keys"), *File);
		Film.Empty();
		return;
	}
	FilmOut = FPaths::ProjectSavedDir() / TEXT("Film");
	FParse::Value(FCommandLine::Get(), TEXT("PantheonFilmOut="), FilmOut);
	FParse::Value(FCommandLine::Get(), TEXT("PantheonFilmFps="), FilmFps);
	FParse::Value(FCommandLine::Get(), TEXT("PantheonFilmStep="), FilmStep);
	FParse::Value(FCommandLine::Get(), TEXT("PantheonFilmSpeed="), FilmSpeed);
	FilmSpeed = FMath::Clamp(FilmSpeed, 0.1f, 10.0f);
	float Warm = 6.0f;
	FParse::Value(FCommandLine::Get(), TEXT("PantheonFilmWarm="), Warm);
	FilmFps = FMath::Clamp(FilmFps, 1.0f, 120.0f);
	FilmStep = FMath::Max(FilmStep, 1);
	FilmWarmFrames = FMath::RoundToInt(Warm * FilmFps);
	FApp::SetUseFixedTimeStep(true);
	FApp::SetFixedDeltaTime(FilmSpeed / FilmFps);
	bShowHelp = false;
	bHelpTimedOut = true;
	UE_LOG(LogTemp, Display, TEXT("PantheonFilm: %d keys, %.1f s at %.0f fps, frames to %s"), Film.Num(), Film.Last().Time, FilmFps, *FilmOut);
}

void APantheonVisitor::TickFilm()
{
	++FilmTick;
	const int32 Frame = FilmTick - FilmWarmFrames;
	const float Time = FMath::Max(Frame, 0) * FilmSpeed / FilmFps;
	if (Time > Film.Last().Time)
	{
		UE_LOG(LogTemp, Display, TEXT("PantheonFilm: done, %d frames"), Frame);
		Film.Empty();
		UKismetSystemLibrary::QuitGame(this, Cast<APlayerController>(GetController()), EQuitPreference::Quit, false);
		return;
	}
	if (Frame == 0)
	{
		SetGhosts(true, FilmPreroll, FilmPriestPreroll);   // the ghosts' time starts with the film
	}

	// the segment the time falls in, and how far through it
	int32 i = 0;
	while (i < Film.Num() - 2 && Film[i + 1].Time <= Time)
	{
		++i;
	}
	const FPantheonFilmKey& A = Film[i];
	const FPantheonFilmKey& B = Film[i + 1];
	const float Span = FMath::Max(B.Time - A.Time, 0.001f);
	const float U = FMath::Clamp((Time - A.Time) / Span, 0.0f, 1.0f);
	// A curve through the keys with matching speed on both sides of each (Hermite, Catmull-Rom
	// tangents in time). A key that only repeats its neighbour is a hold: the camera stops there.
	auto Curve = [&](FVector FPantheonFilmKey::* Member)
	{
		auto Tangent = [&](int32 k)
		{
			if (k <= 0 || k >= Film.Num() - 1 || (Film[k].*Member).Equals(Film[k - 1].*Member, 1.0)
				|| (Film[k + 1].*Member).Equals(Film[k].*Member, 1.0))
			{
				return FVector::ZeroVector;
			}
			return (Film[k + 1].*Member - Film[k - 1].*Member) / FMath::Max(Film[k + 1].Time - Film[k - 1].Time, 0.001f);
		};
		const float U2 = U * U, U3 = U2 * U;
		return (2.0f * U3 - 3.0f * U2 + 1.0f) * (A.*Member) + (U3 - 2.0f * U2 + U) * Span * Tangent(i)
			+ (-2.0f * U3 + 3.0f * U2) * (B.*Member) + (U3 - U2) * Span * Tangent(i + 1);
	};
	FVector Eye = Curve(&FPantheonFilmKey::Position);
	const FVector LookAt = Curve(&FPantheonFilmKey::LookAt);
	// behind a ghost, over its shoulder towards what the keys look at
	bool bFollow = false;
	for (const FFilmFollow& W : FilmFollows)
	{
		const float In = FMath::Clamp((Time - W.T0) / W.Ease, 0.0f, 1.0f);
		const float Out = FMath::Clamp((W.T1 - Time) / W.Ease, 0.0f, 1.0f);
		const float Weight = In * In * (3.0f - 2.0f * In) * Out * Out * (3.0f - 2.0f * Out);
		const AF3GhostDriver* Driver = Cast<AF3GhostDriver>(Ghosts.Get());
		FVector Feet;
		float Tall = 0.0f;
		if (Weight <= 0.0f || !Driver || !Driver->GetGhostPlace(W.Ghost, Feet, Tall))
		{
			continue;
		}
		const FVector Away = (Feet - LookAt).GetSafeNormal2D();
		const FVector Right = FVector::CrossProduct(FVector::UpVector, -Away);
		const FVector Behind = FVector(Feet.X, Feet.Y, 0.0) + Away * (W.Back * 100.0) + Right * (W.Side * 100.0) + FVector(0.0, 0.0, W.Height * 100.0);
		// the ghost's way is made of short straight pieces: the camera rounds them off
		FilmFollowEye = bFilmFollowing ? FMath::Lerp(FilmFollowEye, Behind, 1.0f - FMath::Exp(-FilmSpeed / (0.4f * FilmFps))) : Behind;
		Eye = FMath::Lerp(Eye, FilmFollowEye, Weight);
		bFollow = true;
		break;
	}
	bFilmFollowing = bFollow;
	const float Ease = U * U * (3.0f - 2.0f * U);
	const float Fov = FMath::Lerp(A.Fov, B.Fov, Ease);
	// The keys give the angle across the frame's long side, which is what the engine's field of view
	// means too (it keeps the angle of the major axis), so an upright frame needs no conversion.

	GetCharacterMovement()->SetMovementMode(MOVE_Flying);
	GetCharacterMovement()->StopMovementImmediately();
	SetActorEnableCollision(false);
	SetActorLocation(Eye - FVector(0.0, 0.0, EyeAboveCapsuleCentre), false, nullptr, ETeleportType::None);
	if (Controller)
	{
		Controller->SetControlRotation((LookAt - Eye).Rotation());
	}
	TargetFov = CurrentFov = Fov;
	Camera->SetFieldOfView(Fov);
	CurrentExposure = FMath::Lerp(A.EV, B.EV, Ease);
	Camera->PostProcessSettings.AutoExposureBias = CurrentExposure;

	if (Frame >= 0 && Frame % FilmStep == 0)
	{
		FScreenshotRequest::RequestScreenshot(FilmOut / FString::Printf(TEXT("frame.%05d.png"), Frame / FilmStep), false, false);
	}
}
