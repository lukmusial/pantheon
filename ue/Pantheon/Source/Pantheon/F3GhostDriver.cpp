#include "F3GhostDriver.h"

#include "Animation/AnimationPoseData.h"
#include "Animation/AnimCurveTypes.h"
#include "Animation/AnimSequence.h"
#include "Animation/AttributesRuntime.h"
#include "BoneContainer.h"
#include "BonePose.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/MemStack.h"

namespace
{
	const TCHAR* FogMaterialPath = TEXT("/Game/F3Runtime/MI_GhostFog.MI_GhostFog");
	const TCHAR* MistMaterialPath = TEXT("/Game/F3Runtime/MI_GhostMist.MI_GhostMist");
	const TCHAR* CubePath = TEXT("/Engine/BasicShapes/Cube.Cube");
	const TCHAR* PlanePath = TEXT("/Engine/BasicShapes/Plane.Plane");
	// only its skeleton is used: the reference pose and the animations' bones
	const TCHAR* SkeletonMeshPath = TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple");
	const TCHAR* IdlePath = TEXT("/Game/F3Runtime/MM_Idle.MM_Idle");

	constexpr int32 MaxPrims = 40;     // capsules per ghost; the material's arrays are this long
	constexpr int32 NumGhosts = 5;
	constexpr float BodyPad = 26.0f;   // cm of mist beyond a body capsule: the material's HaloReach + BodyNoise fit in it

	// What each ghost wears and how they are built (user, 2026-11-23: clothing of the period, varied
	// in build and size). Height scales the mannequin (about 183 cm; Romans were shorter); girth
	// scales the trunk and the robes; shoulders their width; stoop bends the spine (1 = a deep bow);
	// speed scales the walking pace.
	// Plain Roman dress only (user, 2026-11-23: veils, hoods, flared skirts, pleats and hanging ends
	// looked ornate and of a later period): everything falls straight, and the one mark of the
	// garment is the drape from the left shoulder across to the right hip.
	enum class EGarb : uint8
	{
		Toga,    // toga over a tunic, to the ankle: the left shoulder and arm wrapped, the right arm free
		Palla,   // a woman's long tunic with the palla draped over it the same way, lighter
		Tunic,   // a plain tunic to the knee, bare shins
	};
	struct FBuildDef
	{
		EGarb Garb;
		bool bFemale;
		float Height;
		float Girth;
		float Shoulders;
		float Stoop;
		float Speed;
	};
	const FBuildDef Builds[NumGhosts] = {
		{EGarb::Toga, false, 0.95f, 1.12f, 0.98f, 0.10f, 1.00f},    // a citizen, sturdy
		{EGarb::Palla, true, 0.87f, 0.96f, 0.80f, 0.12f, 0.95f},   // a matron
		{EGarb::Tunic, false, 0.90f, 1.22f, 0.94f, 0.50f, 0.82f},  // an old man, stout and stooped
		{EGarb::Palla, true, 0.84f, 0.88f, 0.76f, 0.06f, 1.06f},   // a young woman, slight
		{EGarb::Toga, false, 1.00f, 1.00f, 0.94f, 0.08f, 1.00f},   // the priest, tall, his head covered
	};


	// The gods and goddesses on the rotunda floor, in the order the worshippers visit them: azimuth
	// (Blender degrees from +Y, the door, clockwise seen from above) and whether the statue stands in
	// an exedra (deeper) or an aedicula. Jupiter (180) has the priest; the deified emperors in the
	// aediculae at 112.5 (Caesar) and 202.5 (Augustus) are passed by.
	struct FStationDef
	{
		float Azimuth;
		bool bExedra;
	};
	const FStationDef StationDefs[] = {
		{22.5f, false},  // Herakles
		{45.0f, true},   // Apollo Belvedere
		{67.5f, false},  // Apollo Lykeios
		{90.0f, true},   // Venus
		{135.0f, true},  // Neptune
		{157.5f, false}, // Hermes (Farnese)
		{225.0f, true},  // Athena
		{247.5f, false}, // Ceres
		{270.0f, true},  // Ares
		{292.5f, false}, // Hermes Logios
		{315.0f, true},  // Diana
		{337.5f, false}, // Dionysus
	};
	// kneeling distance from the centre (m): a metre or so before the altar fire of an aedicula
	// (20.0 m) or the statue base in an exedra (statue at 24 m); the ring the worshippers walk on
	constexpr float AediculaKneelRadius = 18.6f;
	constexpr float ExedraKneelRadius = 22.3f;
	constexpr float AisleRadius = 15.5f;
	// the priest, before Jupiter's altar (fire at y -19.5 m), facing it
	const FVector2D PriestMetres(0.0, -17.4);

	// Where each statue's painted eyes are (the statue's own space as in Blender, metres), from the
	// painting pipeline: see tools/statue_eyes.py
	struct FEyeDef
	{
		double Centre[3];
		double Out[3];   // unit, from the inner to the outer corner
		double Up[3];    // unit, up the face
		float Width;
		float Offset;
	};
	struct FStatueEyesDef
	{
		const TCHAR* Key;
		FEyeDef Eyes[2];
		float Iris[3];
	};
	const FStatueEyesDef StatueEyes[] = {
#include "F3StatueEyes.inl"
	};
	const TCHAR* StatuePackage = TEXT("/Game/StatuesV2/");

	// Blender's axes to the imported mesh's: y is mirrored; metres to centimetres for positions
	FLinearColor MeshVector(const double V[3], float Scale, float Alpha)
	{
		return FLinearColor(float(V[0]) * Scale, float(-V[1]) * Scale, float(V[2]) * Scale, Alpha);
	}

	// The walk (user, 2026-11-24: smooth, not jumpy). The figure moves at an even speed, eased in and
	// out; the feet are placed, not animated: a foot stays where it was set down while the body passes
	// over it, then swings to its next place. Short, close steps, as in a slow procession (a long
	// stride spreads a long garment into a wide tent).
	constexpr float StepLength = 42.0f;    // cm between one footfall and the next, at the mannequin's size
	constexpr float SwingShare = 0.42f;    // the part of a foot's cycle it spends in the air
	constexpr float StanceWidth = 0.8f;    // the feet stand this far apart, as a share of the hips' width
	constexpr float StepLift = 5.0f;       // how high a swinging foot clears the floor (cm)
	constexpr float PathEase = 0.7f;       // s to gather and lose speed
	constexpr float TurnEase = 0.5f;       // s to begin and end a turn
	constexpr float TurnRate = 65.0f;      // degrees/s at most

	FVector ToUnrealCm(const FVector2D& M) { return FVector(M.X * 100.0, -M.Y * 100.0, 0.0); }

	FVector OnRing(float AzimuthDeg, float RadiusM)
	{
		const float A = FMath::DegreesToRadians(AzimuthDeg);
		return ToUnrealCm(FVector2D(RadiusM * FMath::Sin(A), RadiusM * FMath::Cos(A)));
	}

	FQuat AboutX(float Deg) { return FQuat(FVector(1.0, 0.0, 0.0), FMath::DegreesToRadians(Deg)); }

	/** A value drawn towards its target without a jolt (critically damped), never faster than MaxSpeed. */
	float SmoothDamp(float Current, float Target, float& Velocity, float SmoothTime, float MaxSpeed, float Dt)
	{
		if (Dt <= 0.0f)
		{
			return Current;
		}
		SmoothTime = FMath::Max(SmoothTime, 0.01f);
		const float Omega = 2.0f / SmoothTime;
		const float X = Omega * Dt;
		const float Exp = 1.0f / (1.0f + X + 0.48f * X * X + 0.235f * X * X * X);
		const float MaxChange = MaxSpeed * SmoothTime;
		const float Change = FMath::Clamp(Current - Target, -MaxChange, MaxChange);
		const float Aim = Current - Change;
		const float Temp = (Velocity + Omega * Change) * Dt;
		Velocity = (Velocity - Omega * Temp) * Exp;
		float Out = Aim + (Change + Temp) * Exp;
		if ((Target - Current > 0.0f) == (Out > Target))
		{
			Out = Target;
			Velocity = 0.0f;
		}
		return Out;
	}

	float SmoothDampAngle(float Yaw, float Desired, float& Rate, float SmoothTime, float MaxRate, float Dt)
	{
		const float Target = Yaw + FMath::FindDeltaAngleDegrees(Yaw, Desired);
		return FRotator::NormalizeAxis(SmoothDamp(Yaw, Target, Rate, SmoothTime, MaxRate, Dt));
	}

	void SamplePath(const TArray<FVector>& P, const TArray<float>& L, float D, FVector& OutPos, FVector& OutDir)
	{
		int32 Seg = 1;
		while (Seg < L.Num() - 1 && L[Seg] < D)
		{
			++Seg;
		}
		const float T = FMath::Clamp((D - L[Seg - 1]) / FMath::Max(L[Seg] - L[Seg - 1], 0.01f), 0.0f, 1.0f);
		OutPos = FMath::Lerp(P[Seg - 1], P[Seg], T);
		OutDir = (P[Seg] - P[Seg - 1]).GetSafeNormal2D();
	}

	/** Two-bone IK: the elbow for a shoulder and a hand target (pulled in if out of reach), bent towards Pole. */
	FVector SolveElbow(const FVector& Shoulder, FVector& Hand, float Upper, float Fore, const FVector& Pole)
	{
		FVector D = Hand - Shoulder;
		float Dist = D.Size();
		const float Reach = (Upper + Fore) * 0.985f;
		if (Dist > Reach)
		{
			Hand = Shoulder + D * (Reach / Dist);
			D = Hand - Shoulder;
			Dist = Reach;
		}
		Dist = FMath::Max(Dist, FMath::Abs(Upper - Fore) + 1.0f);
		const FVector Dir = D.GetSafeNormal();
		const float Along = (Upper * Upper - Fore * Fore + Dist * Dist) / (2.0f * Dist);
		const float Out = FMath::Sqrt(FMath::Max(Upper * Upper - Along * Along, 0.0f));
		FVector Perp = Pole - Dir * FVector::DotProduct(Pole, Dir);
		if (!Perp.Normalize())
		{
			Perp = FVector::CrossProduct(Dir, FVector::UpVector).GetSafeNormal();
		}
		return Shoulder + Dir * Along + Perp * Out;
	}
}

void AF3GhostDriver::FEase::Step(float Dt, float SmoothTime)
{
	// critically damped spring towards the target (no overshoot)
	const float Omega = 2.0f / FMath::Max(SmoothTime, 0.01f);
	const float X = Omega * Dt;
	const float Exp = 1.0f / (1.0f + X + 0.48f * X * X + 0.235f * X * X * X);
	const float Change = Value - Target;
	const float Temp = (Velocity + Omega * Change) * Dt;
	Velocity = (Velocity - Omega * Temp) * Exp;
	Value = Target + (Change + Temp) * Exp;
}

AF3GhostDriver::AF3GhostDriver()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;   // after the camera has moved: the quads face it
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void AF3GhostDriver::BeginPlay()
{
	Super::BeginPlay();
	if (bSpawnScene)
	{
		SpawnScene();
	}
}

void AF3GhostDriver::EndPlay(const EEndPlayReason::Type Reason)
{
	for (const TWeakObjectPtr<AActor>& A : Spawned)
	{
		if (A.IsValid())
		{
			A->Destroy();
		}
	}
	// the statues get their own materials back: their eyes look ahead again
	for (const FStatueLook& L : StatueLooks)
	{
		if (UStaticMeshComponent* C = L.Component.Get())
		{
			C->SetMaterial(L.Slot, L.Original.Get());
		}
	}
	StatueLooks.Reset();
	FlushTrace();
	Spawned.Reset();
	Ghosts.Reset();
	bReady = false;
	Super::EndPlay(Reason);
}

void AF3GhostDriver::SpawnScene()
{
	UWorld* World = GetWorld();
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	// fog volume over the rotunda floor and into the exedrae, 0-4 m: only where the fog is, so the
	// shader runs on as few volumetric-fog cells as possible
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, CubePath);
	UMaterialInterface* FogMat = LoadObject<UMaterialInterface>(nullptr, FogMaterialPath);
	// -PantheonGhostNoFog and -PantheonGhostNoMist leave out the floor fog or the figures, to measure
	// what each costs
	const bool bNoFog = FParse::Param(FCommandLine::Get(), TEXT("PantheonGhostNoFog"));
	bNoMist = FParse::Param(FCommandLine::Get(), TEXT("PantheonGhostNoMist"));
	if (bNoFog)
	{
	}
	else if (Cube && FogMat)
	{
		AStaticMeshActor* Fog = World->SpawnActor<AStaticMeshActor>(FVector(0.0, 0.0, 200.0), FRotator::ZeroRotator, Params);
		Fog->SetMobility(EComponentMobility::Movable);
		UStaticMeshComponent* C = Fog->GetStaticMeshComponent();
		C->SetStaticMesh(Cube);
		C->SetMaterial(0, FogMat);
		C->SetCastShadow(false);
		C->SetVisibleInRayTracing(false);
		Fog->SetActorScale3D(FVector(50.0, 50.0, 4.0));
		// the whole actor, not just the component: the box blocked the visitor at its edge (the
		// doorway) and held anyone inside it (user, 2026-11-23)
		C->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
		Fog->SetActorEnableCollision(false);
		Spawned.Add(Fog);
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("F3GhostDriver: fog assets missing (%s)"), FogMaterialPath);
	}

	FollowWithStatueEyes();

	Stations.Reset();
	for (const FStationDef& D : StationDefs)
	{
		FStation S;
		S.Azimuth = D.Azimuth;
		S.Kneel = OnRing(D.Azimuth, D.bExedra ? ExedraKneelRadius : AediculaKneelRadius);
		S.Aisle = OnRing(D.Azimuth, AisleRadius);
		S.FaceYaw = (S.Kneel - S.Aisle).Rotation().Yaw;
		Stations.Add(S);
	}

	IdleAnim = LoadObject<UAnimSequence>(nullptr, IdlePath);
	if (!IdleAnim || !InitRig())
	{
		UE_LOG(LogTemp, Warning, TEXT("F3GhostDriver: the mannequin's skeleton or animations are missing"));
		return;
	}
	PrimTexture = UTexture2D::CreateTransient(MaxPrims, 3 * NumGhosts, PF_A32B32G32R32F);
	PrimTexture->SRGB = false;
	PrimTexture->Filter = TF_Nearest;
	PrimTexture->CompressionSettings = TC_HDR;
	PrimTexture->UpdateResource();
	// -PantheonGhostSolid draws the ghosts dense and hard-edged, to check the shapes and poses
	bSolid = FParse::Param(FCommandLine::Get(), TEXT("PantheonGhostSolid"));
	// -PantheonGhostLineup stands the five in a row in the middle of the rotunda, facing the door,
	// to compare their builds, garments and poses
	bLineup = FParse::Param(FCommandLine::Get(), TEXT("PantheonGhostLineup"));
	if (FParse::Value(FCommandLine::Get(), TEXT("PantheonGhostTrace="), TraceFile))
	{
		FFileHelper::SaveStringToFile(TEXT("t,ghost,state,x,y,yaw,speed,kneel,bow,orans,headx,heady,headz,pelvisz,lx,ly,lz,rx,ry,rz,hlx,hly,hlz,hrx,hry,hrz\n"), *TraceFile);
	}

	// four worshippers spread round the ring, men and women alternating, and the priest
	for (int32 i = 0; i < NumGhosts; ++i)
	{
		SpawnGhost(i, i == NumGhosts - 1);
	}
	// as if they had been about for a while already
	for (float T = 0.0f; T < PrerollSeconds + PriestPrerollSeconds; T += 1.0f / 30.0f)
	{
		for (FGhost& G : Ghosts)
		{
			if (T < PrerollSeconds || G.bPriest)
			{
				StepGhost(G, 1.0f / 30.0f);
			}
		}
	}
	bReady = Ghosts.Num() > 0;
	UE_LOG(LogTemp, Display, TEXT("F3GhostDriver: %d ghosts, %.0f s in"), Ghosts.Num(), PrerollSeconds);
}

void AF3GhostDriver::FollowWithStatueEyes()
{
	// In ghost mode the statues' eyes follow the visitor (user, 2026-11-23). Each statue gets a
	// dynamic instance of its material that knows where its two painted eyes are; the material
	// (pantheon_materials.statue_eyes) then slides the iris towards the camera. Nothing ticks.
	int32 Count = 0;
	for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
	{
		UStaticMeshComponent* C = It->GetStaticMeshComponent();
		const UStaticMesh* Mesh = C ? C->GetStaticMesh().Get() : nullptr;
		if (!Mesh || !Mesh->GetPathName().StartsWith(StatuePackage))
		{
			continue;
		}
		const FStatueEyesDef* Def = nullptr;
		for (const FStatueEyesDef& D : StatueEyes)
		{
			if (Mesh->GetName() == D.Key)
			{
				Def = &D;
				break;
			}
		}
		if (!Def)
		{
			continue;
		}
		for (int32 Slot = 0; Slot < C->GetNumMaterials(); ++Slot)
		{
			UMaterialInterface* Original = C->GetMaterial(Slot);
			if (!Original)
			{
				continue;
			}
			UMaterialInstanceDynamic* M = C->CreateDynamicMaterialInstance(Slot, Original);
			const TCHAR* Names[2][3] = {{TEXT("EyeAC"), TEXT("EyeAU"), TEXT("EyeAV")}, {TEXT("EyeBC"), TEXT("EyeBU"), TEXT("EyeBV")}};
			for (int32 e = 0; e < 2; ++e)
			{
				const FEyeDef& E = Def->Eyes[e];
				M->SetVectorParameterValue(Names[e][0], MeshVector(E.Centre, 100.0f, E.Width * 100.0f));
				M->SetVectorParameterValue(Names[e][1], MeshVector(E.Out, 1.0f, E.Offset));
				M->SetVectorParameterValue(Names[e][2], MeshVector(E.Up, 1.0f, 0.0f));
			}
			M->SetVectorParameterValue(TEXT("EyeIris"), FLinearColor(Def->Iris[0], Def->Iris[1], Def->Iris[2], 1.0f));
			M->SetScalarParameterValue(TEXT("EyesFollow"), 1.0f);
			FStatueLook L;
			L.Component = C;
			L.Slot = Slot;
			L.Original = Original;
			StatueLooks.Add(L);
		}
		++Count;
	}
	UE_LOG(LogTemp, Display, TEXT("F3GhostDriver: the eyes of %d statues follow the visitor"), Count);
}

bool AF3GhostDriver::InitRig()
{
	SkeletonMesh = LoadObject<USkeletalMesh>(nullptr, SkeletonMeshPath);
	if (!SkeletonMesh)
	{
		return false;
	}
	const FReferenceSkeleton& Ref = SkeletonMesh->GetRefSkeleton();
	const int32 N = Ref.GetNum();
	TArray<FBoneIndexType> Required;
	for (int32 i = 0; i < N; ++i)
	{
		Required.Add(FBoneIndexType(i));
	}
	Bones = MakeShared<FBoneContainer>(Required, UE::Anim::FCurveFilterSettings(UE::Anim::ECurveFilterMode::DisallowAll), *SkeletonMesh);

	FRig& R = Rig;
	bool bAll = true;
	auto Find = [&Ref, &bAll](const FString& Name)
	{
		const int32 Index = Ref.FindBoneIndex(FName(*Name));
		if (Index == INDEX_NONE)
		{
			UE_LOG(LogTemp, Warning, TEXT("F3GhostDriver: bone %s missing"), *Name);
			bAll = false;
		}
		return Index;
	};
	R.Root = Find(TEXT("root"));
	R.Pelvis = Find(TEXT("pelvis"));
	for (int32 k = 0; k < 5; ++k)
	{
		R.Spine[k] = Find(FString::Printf(TEXT("spine_%02d"), k + 1));
	}
	R.Neck = Find(TEXT("neck_01"));
	R.Head = Find(TEXT("head"));
	const TCHAR* Sides[2] = {TEXT("_l"), TEXT("_r")};
	for (int32 s = 0; s < 2; ++s)
	{
		R.Thigh[s] = Find(FString(TEXT("thigh")) + Sides[s]);
		R.Calf[s] = Find(FString(TEXT("calf")) + Sides[s]);
		R.Foot[s] = Find(FString(TEXT("foot")) + Sides[s]);
		R.Ball[s] = Find(FString(TEXT("ball")) + Sides[s]);
		R.UpperArm[s] = Find(FString(TEXT("upperarm")) + Sides[s]);
		R.LowerArm[s] = Find(FString(TEXT("lowerarm")) + Sides[s]);
		R.Hand[s] = Find(FString(TEXT("hand")) + Sides[s]);
	}
	if (!bAll)
	{
		return false;
	}

	// measures of the reference pose, in the figure's own space
	TArray<FTransform> CS;
	CS.SetNum(N);
	for (int32 i = 0; i < N; ++i)
	{
		const int32 P = Ref.GetParentIndex(i);
		CS[i] = P >= 0 ? Ref.GetRefBonePose()[i] * CS[P] : Ref.GetRefBonePose()[i];
	}
	auto At = [&CS](int32 Bone) { return CS[Bone].GetLocation(); };
	// kneeling: the knee rests about 9 cm above the floor, the thigh tilted forward by the kneel's
	// hip angle; the pelvis comes down by the difference from its standing height
	const float Thigh = FVector::Dist(At(R.Thigh[0]), At(R.Calf[0]));
	R.KneelDrop = At(R.Pelvis).Z - (9.0f + Thigh * FMath::Cos(FMath::DegreesToRadians(22.0f)));
	R.ThighLength = Thigh;
	R.CalfLength = FVector::Dist(At(R.Calf[0]), At(R.Foot[0]));
	R.KneelBack = R.CalfLength - Thigh * FMath::Sin(FMath::DegreesToRadians(22.0f));
	R.HipX = FMath::Abs(At(R.Thigh[0]).X);
	R.HipZ = At(R.Thigh[0]).Z;
	R.AnkleZ = At(R.Foot[0]).Z;
	R.BallZ = At(R.Ball[0]).Z;
	R.FootLength = FVector::Dist(At(R.Foot[0]), At(R.Ball[0]));
	R.UpperArmLength = FVector::Dist(At(R.UpperArm[0]), At(R.LowerArm[0]));
	R.ForeArmLength = FVector::Dist(At(R.LowerArm[0]), At(R.Hand[0]));
	const FQuat HeadRot = CS[R.Head].GetRotation();
	R.HeadUpLocal = HeadRot.UnrotateVector(FVector(0.0, 0.0, 1.0));
	R.HeadForwardLocal = HeadRot.UnrotateVector(FVector(0.0, 1.0, 0.0));
	R.bValid = true;
	UE_LOG(LogTemp, Display, TEXT("F3GhostDriver: rig pelvis %.0f spine2 %.0f spine4 %.0f neck %.0f head %.0f shoulder %.0f/%.0f hip %.0f/%.0f knee %.0f ankle %.0f, arm %.0f+%.0f, kneel drop %.0f"),
		At(R.Pelvis).Z, At(R.Spine[1]).Z, At(R.Spine[3]).Z, At(R.Neck).Z, At(R.Head).Z, At(R.UpperArm[0]).Z, At(R.UpperArm[0]).X,
		At(R.Thigh[0]).Z, At(R.Thigh[0]).X, At(R.Calf[0]).Z, At(R.Foot[0]).Z, R.UpperArmLength, R.ForeArmLength, R.KneelDrop);
	return true;
}

void AF3GhostDriver::SpawnGhost(int32 Index, bool bPriest)
{
	UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, PlanePath);
	UMaterialInterface* MistMat = LoadObject<UMaterialInterface>(nullptr, MistMaterialPath);
	if (!Plane || !MistMat)
	{
		UE_LOG(LogTemp, Warning, TEXT("F3GhostDriver: %s missing"), MistMaterialPath);
		return;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AStaticMeshActor* Quad = GetWorld()->SpawnActor<AStaticMeshActor>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
	Quad->SetMobility(EComponentMobility::Movable);
	UStaticMeshComponent* C = Quad->GetStaticMeshComponent();
	C->SetStaticMesh(Plane);
	C->SetMaterial(0, MistMat);
	C->SetCastShadow(false);
	C->SetVisibleInRayTracing(false);
	C->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
	Quad->SetActorEnableCollision(false);
	Quad->SetActorHiddenInGame(bNoMist);
	UMaterialInstanceDynamic* Mist = C->CreateAndSetMaterialInstanceDynamic(0);
	Mist->SetTextureParameterValue(TEXT("PrimData"), PrimTexture);
	Mist->SetScalarParameterValue(TEXT("Row"), float(Index));
	Mist->SetScalarParameterValue(TEXT("Count"), 0.0f);
	if (bPriest)
	{
		// He stands in the brightest place in the room, before the altar fire and the sunlit statue.
		// Mist as thin and as dimly lit as the others' is a faint smoke there, not a figure (seen from
		// behind, close, in the film of 2026-11-24): his is denser and has a light of its own.
		Mist->SetScalarParameterValue(TEXT("Density"), 0.06f);
		Mist->SetVectorParameterValue(TEXT("GhostGlow"), FLinearColor(1.28f, 1.38f, 1.5f, 1.0f));
	}
	if (bSolid)
	{
		Mist->SetScalarParameterValue(TEXT("Density"), 0.6f);
		Mist->SetScalarParameterValue(TEXT("Soft"), 2.0f);
		Mist->SetScalarParameterValue(TEXT("BodyNoise"), 0.0f);
		Mist->SetScalarParameterValue(TEXT("TrailDensity"), 0.03f);
		Mist->SetScalarParameterValue(TEXT("FeetLow"), 1.0f);
		Mist->SetScalarParameterValue(TEXT("Halo"), 0.0f);
	}
	Spawned.Add(Quad);

	FGhost& G = Ghosts.AddDefaulted_GetRef();
	G.Quad = Quad;
	G.Mist = Mist;
	G.Build = Index;
	G.bPriest = bPriest;
	G.Rand.Initialize(1723 + Index * 71);
	G.IdleTime = G.Rand.FRandRange(0.0f, 5.0f);
	G.FirstFoot = Index % 2;
	if (bPriest)
	{
		G.Position = ToUnrealCm(PriestMetres);
		G.Yaw = 90.0f;   // facing Jupiter (Blender -Y)
		G.State = EGhostState::PriestStand;
	}
	else
	{
		// start on their knees at every third altar, each ready to rise at a different moment
		G.Station = G.Target = (Index * 3) % Stations.Num();
		G.Position = Stations[G.Station].Kneel;
		G.Yaw = Stations[G.Station].FaceYaw;
		G.State = EGhostState::Kneel;
		G.Kneel.Set(1.0f);
		G.Bow.Set(1.0f);
		G.Hold = G.Rand.FRandRange(2.0f, 8.0f) + Index * 4.0f;
	}
	if (bLineup)
	{
		G.Position = ToUnrealCm(FVector2D((Index - 2) * 1.5, 2.0));
		G.Yaw = -90.0f;   // facing the door (Blender +Y)
		G.Station = G.Target = Index;
		G.Kneel.Set(0.0f);
		G.Bow.Set(0.0f);
	}
	PoseGhost(G);
}

bool AF3GhostDriver::GetGhostPlace(int32 Index, FVector& OutFeet, float& OutHeight) const
{
	if (!Ghosts.IsValidIndex(Index))
	{
		return false;
	}
	OutFeet = Ghosts[Index].Position;
	OutHeight = 174.0f * Builds[Ghosts[Index].Build].Height;
	return true;
}

bool AF3GhostDriver::StationFree(const FGhost& G, int32 S) const
{
	for (const FGhost& O : Ghosts)
	{
		if (&O != &G && !O.bPriest && (O.Station == S || O.Target == S))
		{
			return false;
		}
	}
	return true;
}

void AF3GhostDriver::PlanPath(FGhost& G, int32 From, int32 To)
{
	// out to the ring, along it (clockwise, the way the stations are listed), in to the next altar
	TArray<FVector> P;
	P.Add(G.Position);
	P.Add(Stations[From].Aisle);
	const float A0 = Stations[From].Azimuth;
	const float Span = FMath::Fmod(Stations[To].Azimuth - A0 + 360.0f, 360.0f);
	const int32 Steps = FMath::Max(1, FMath::CeilToInt(Span / 7.5f));
	for (int32 k = 1; k < Steps; ++k)
	{
		P.Add(OnRing(A0 + Span * k / Steps, AisleRadius));
	}
	P.Add(Stations[To].Aisle);
	P.Add(Stations[To].Kneel);
	// round the corners (Chaikin, end points kept)
	for (int32 Pass = 0; Pass < 5; ++Pass)
	{
		TArray<FVector> Q;
		Q.Add(P[0]);
		for (int32 i = 0; i + 1 < P.Num(); ++i)
		{
			if (i > 0)
			{
				Q.Add(FMath::Lerp(P[i], P[i + 1], 0.25f));
			}
			if (i + 2 < P.Num())
			{
				Q.Add(FMath::Lerp(P[i], P[i + 1], 0.75f));
			}
		}
		Q.Add(P.Last());
		P = MoveTemp(Q);
	}
	G.Path = MoveTemp(P);
	G.PathLength.Reset();
	G.PathLength.Add(0.0f);
	for (int32 i = 1; i < G.Path.Num(); ++i)
	{
		G.PathLength.Add(G.PathLength.Last() + FVector::Dist(G.Path[i - 1], G.Path[i]));
	}
	G.PathPos = 0.0f;
	G.Speed = 0.0f;
}

void AF3GhostDriver::StepWorshipper(FGhost& G, float Dt)
{
	const FBuildDef& B = Builds[G.Build];
	const float Pace = WalkSpeed * B.Speed;
	switch (G.State)
	{
	case EGhostState::Walk:
	{
		// Along the path at an even pace: speed gathers and is lost gradually (it falls away over the
		// last two paces before the altar), and the figure turns towards its way before setting off.
		// The steps follow from the movement (StepFeet), not the movement from the steps.
		const float Total = G.PathLength.Last();
		FVector Pos, Dir;
		SamplePath(G.Path, G.PathLength, G.PathPos, Pos, Dir);
		const float Turn = FMath::Abs(FMath::FindDeltaAngleDegrees(G.Yaw, Dir.Rotation().Yaw));
		const float Go = FMath::Clamp((75.0f - Turn) / 50.0f, 0.0f, 1.0f);
		G.PathPos = SmoothDamp(G.PathPos, Total, G.Speed, PathEase, Pace * Go, Dt);
		SamplePath(G.Path, G.PathLength, G.PathPos, Pos, Dir);
		G.Position = Pos;
		// (eased as well: the path is made of short straight pieces, and the feet aim by this)
		G.Velocity += (FVector2D(Dir.X, Dir.Y) * G.Speed - G.Velocity) * (1.0f - FMath::Exp(-Dt / 0.2f));
		G.Yaw = SmoothDampAngle(G.Yaw, Dir.Rotation().Yaw, G.YawRate, TurnEase, TurnRate, Dt);
		if (Total - G.PathPos < 0.5f && G.Speed < 2.0f)
		{
			G.Station = G.Target;
			G.Speed = 0.0f;
			G.Velocity = FVector2D::ZeroVector;
			G.State = EGhostState::Arrive;
			G.StateTime = 0.0f;
		}
		break;
	}
	case EGhostState::Arrive:
		// stands a moment, the feet coming together, before going down
		G.Yaw = SmoothDampAngle(G.Yaw, Stations[G.Station].FaceYaw, G.YawRate, TurnEase, TurnRate, Dt);
		if (G.StateTime > 2.4f && G.Feet[0].U >= 1.0f && G.Feet[1].U >= 1.0f)
		{
			G.State = EGhostState::KneelDown;
			G.StateTime = 0.0f;
		}
		break;
	case EGhostState::KneelDown:
		G.Yaw = SmoothDampAngle(G.Yaw, Stations[G.Station].FaceYaw, G.YawRate, TurnEase, TurnRate, Dt);
		G.Kneel.Target = 1.0f;
		if (G.StateTime > 1.6f)
		{
			G.Bow.Target = 1.0f;
		}
		if (G.StateTime > 4.0f)
		{
			G.State = EGhostState::Kneel;
			G.StateTime = 0.0f;
			G.Hold = G.Rand.FRandRange(KneelSecondsMin, KneelSecondsMax);
		}
		break;
	case EGhostState::Kneel:
	{
		// stay on the knees past the time while the next altar is taken
		const int32 Next = (G.Station + 1) % Stations.Num();
		if (G.StateTime > G.Hold && StationFree(G, Next))
		{
			G.Target = Next;
			G.State = EGhostState::Rise;
			G.StateTime = 0.0f;
		}
		break;
	}
	case EGhostState::Rise:
		G.Bow.Target = 0.0f;
		if (G.StateTime > 1.2f)
		{
			G.Kneel.Target = 0.0f;
		}
		if (G.StateTime > 5.0f)
		{
			PlanPath(G, G.Station, G.Target);
			G.State = EGhostState::Walk;
			G.StateTime = 0.0f;
		}
		break;
	default:
		break;
	}
}

void AF3GhostDriver::StepPriest(FGhost& G, float Dt)
{
	// stands; raises his hands in prayer; lowers them; kneels with head bowed, longer; rises
	auto Next = [&G](EGhostState S)
	{
		G.State = S;
		G.StateTime = 0.0f;
	};
	switch (G.State)
	{
	case EGhostState::PriestStand:
		G.Orans.Target = G.Kneel.Target = G.Bow.Target = 0.0f;
		if (G.StateTime > 3.0f)
		{
			Next(EGhostState::PriestOrans);
		}
		break;
	case EGhostState::PriestOrans:
		G.Orans.Target = 1.0f;
		if (G.StateTime > 9.0f)
		{
			Next(EGhostState::PriestLower);
		}
		break;
	case EGhostState::PriestLower:
		G.Orans.Target = 0.0f;
		if (G.StateTime > 3.2f)
		{
			Next(EGhostState::PriestKneel);
		}
		break;
	case EGhostState::PriestKneel:
		G.Kneel.Target = 1.0f;
		if (G.StateTime > 1.6f)
		{
			G.Bow.Target = 1.0f;
		}
		if (G.StateTime > 20.0f)
		{
			Next(EGhostState::PriestRise);
		}
		break;
	case EGhostState::PriestRise:
		G.Bow.Target = 0.0f;
		if (G.StateTime > 1.2f)
		{
			G.Kneel.Target = 0.0f;
		}
		if (G.StateTime > 5.0f)
		{
			Next(EGhostState::PriestStand);
		}
		break;
	default:
		break;
	}
}

void AF3GhostDriver::StepGhost(FGhost& G, float Dt)
{
	G.StateTime += Dt;
	G.IdleTime += Dt;
	if (bLineup)
	{
		// stand in a row (the priest with raised hands), then kneel, in turn
		const bool bKneel = FMath::Fmod(G.StateTime, 24.0f) > 12.0f;
		G.Orans.Target = bKneel || !G.bPriest ? 0.0f : 1.0f;
		G.Kneel.Target = G.Bow.Target = bKneel ? 1.0f : 0.0f;
	}
	else if (G.bPriest)
	{
		StepPriest(G, Dt);
	}
	else if (Stations.Num() > 0)
	{
		StepWorshipper(G, Dt);
	}
	// unhurried: down onto the knees and up again, the bow and the raising of the hands each take
	// two to three seconds, starting and ending gently
	G.Kneel.Step(Dt, 1.0f);
	G.Bow.Step(Dt, 0.8f);
	G.Orans.Step(Dt, 1.0f);
	StepFeet(G, Dt);
	PoseGhost(G);
}

void AF3GhostDriver::StepFeet(FGhost& G, float Dt) const
{
	// Each foot has its place under the figure, beside the other. A foot on the ground stays where it
	// is in the world while the figure moves on. The two take turns to step: a step lasts a fixed
	// time and lands ahead of the foot's place by as much as the figure will travel during half the
	// time the foot then stands, so that at an even pace the figure passes over each foot evenly. When
	// the figure slows the steps shorten; when it stops or turns on the spot the feet step to their
	// places and then rest.
	const FBuildDef& B = Builds[G.Build];
	const FTransform ToWorld(FRotator(0.0, G.Yaw - 90.0, 0.0), G.Position, FVector(B.Height));
	const float HalfWidth = Rig.HipX * StanceWidth;
	FVector2D Home[2];
	for (int32 s = 0; s < 2; ++s)
	{
		Home[s] = FVector2D(ToWorld.TransformPosition(FVector(s == 0 ? HalfWidth : -HalfWidth, 0.0, 0.0)));
	}
	if (!G.bFeetKnown)
	{
		for (int32 s = 0; s < 2; ++s)
		{
			G.Feet[s] = FFoot();
			G.Feet[s].Pos = G.Feet[s].From = Home[s];
			G.Feet[s].Yaw = G.Feet[s].FromYaw = G.Yaw;
		}
		G.bFeetKnown = true;
		G.bGaitActive = false;
	}
	const float Cycle = 2.0f * StepLength * B.Height / FMath::Max(WalkSpeed * B.Speed, 1.0f);
	const float SwingTime = SwingShare * Cycle;
	const float Lead = 0.5f * (Cycle - SwingTime);
	float Off[2];
	bool bWants[2];
	for (int32 s = 0; s < 2; ++s)
	{
		Off[s] = float(FVector2D::Distance(G.Feet[s].Pos, Home[s]));
		bWants[s] = G.Speed > 1.5f || Off[s] > 5.0f * B.Height || FMath::Abs(FMath::FindDeltaAngleDegrees(G.Feet[s].Yaw, G.Yaw)) > 12.0f;
	}
	auto Lift = [&G](int32 s)
	{
		FFoot& F = G.Feet[s];
		F.From = F.Pos;
		F.FromYaw = F.Yaw;
		F.U = 0.0f;
	};
	const bool bActive = G.Feet[0].U < 1.0f || G.Feet[1].U < 1.0f || bWants[0] || bWants[1];
	if (bActive && !G.bGaitActive)
	{
		// setting off from rest: the foot further from its place leads, at once
		const int32 First = FMath::Abs(Off[0] - Off[1]) > 2.0f ? (Off[0] > Off[1] ? 0 : 1) : G.FirstFoot;
		G.FirstFoot = 1 - First;
		G.GaitClock = First == 0 ? 0.0f : 0.5f;
		Lift(First);
	}
	else if (bActive)
	{
		const float Before = G.GaitClock;
		G.GaitClock += Dt / Cycle;
		for (int32 s = 0; s < 2; ++s)
		{
			const float Offset = s == 0 ? 0.0f : 0.5f;
			if (FMath::FloorToInt(G.GaitClock - Offset) > FMath::FloorToInt(Before - Offset) && bWants[s]
				&& G.Feet[0].U >= 1.0f && G.Feet[1].U >= 1.0f)
			{
				Lift(s);
			}
		}
		if (G.GaitClock >= 1.0f)
		{
			G.GaitClock -= 1.0f;
		}
	}
	G.bGaitActive = bActive;
	for (int32 s = 0; s < 2; ++s)
	{
		FFoot& F = G.Feet[s];
		if (F.U >= 1.0f)
		{
			F.Lift = 0.0f;
			continue;
		}
		F.U = FMath::Min(1.0f, F.U + Dt / SwingTime);
		const FVector2D Ahead = (G.Velocity * ((1.0f - F.U) * SwingTime + Lead)).GetClampedToMaxSize(0.8f * StepLength * B.Height);
		const FVector2D Target = Home[s] + Ahead;
		const float S = F.U * F.U * F.U * (F.U * (F.U * 6.0f - 15.0f) + 10.0f);   // leaves and lands without a jolt
		F.Pos = FMath::Lerp(F.From, Target, S);
		F.Yaw = FRotator::NormalizeAxis(F.FromYaw + FMath::FindDeltaAngleDegrees(F.FromYaw, G.Yaw) * S);
		const float Up = FMath::Sin(PI * F.U);
		F.Lift = StepLift * B.Height * Up * Up * FMath::Clamp(float(FVector2D::Distance(F.From, Target)) / 25.0f, 0.25f, 1.0f);
	}
}

void AF3GhostDriver::PoseGhost(FGhost& G) const
{
	if (!Rig.bValid || !SkeletonMesh || !IdleAnim || !Bones.IsValid())
	{
		return;
	}
	const FBuildDef& B = Builds[G.Build];
	const FRig& R = Rig;
	const FReferenceSkeleton& Ref = SkeletonMesh->GetRefSkeleton();
	const int32 N = Ref.GetNum();
	TArray<FTransform>& Local = G.Local;
	if (Local.Num() != N)
	{
		Local = Ref.GetRefBonePose();
	}

	// base pose: the idle animation (breathing, a little sway); the arms and the legs are placed
	// afterwards, by IK
	{
		FMemMark Mark(FMemStack::Get());
		FCompactPose IdlePose;
		FBlendedCurve Curve;
		UE::Anim::FStackAttributeContainer Attributes;
		IdlePose.SetBoneContainer(Bones.Get());
		IdlePose.ResetToRefPose();
		Curve.InitFrom(*Bones);
		{
			FAnimationPoseData Data(IdlePose, Curve, Attributes);
			IdleAnim->GetAnimationPose(Data, FAnimExtractContext(double(FMath::Fmod(G.IdleTime, IdleAnim->GetPlayLength())), false));
		}
		for (int32 i = 0; i < N; ++i)
		{
			const FCompactPoseBoneIndex C = Bones->MakeCompactPoseIndex(FMeshPoseBoneIndex(i));
			Local[i] = C.IsValid() ? IdlePose[C] : Ref.GetRefBonePose()[i];
		}
		Local[R.Root] = Ref.GetRefBonePose()[R.Root];   // no root motion: the driver moves the figure
	}

	// Bowing, as extra rotations about the figure's own axes (it faces +Y, its left is +X, up is +Z):
	// a positive angle about X tilts an upright bone back. The head is a little bowed whenever the
	// hands are not raised (user, 2026-11-23: head slightly bowed while walking); the build's stoop
	// bends the spine for good.
	const float K = G.Kneel.Value;
	const float O = G.Orans.Value;
	const float SpineW = G.Bow.Value + B.Stoop;
	const float HeadW = FMath::Max(G.Bow.Value, 0.6f * (1.0f - O));

	// The feet, in the figure's own space. Kneeling, the right leg goes first and the left follows
	// (rising, the left foot comes forward first): each foot slides back until the shin lies on the
	// floor, while the pelvis comes down; the knees follow from where hip and ankle are.
	const FTransform ToWorld(FRotator(0.0, G.Yaw - 90.0, 0.0), G.Position, FVector(B.Height));
	FVector Ankle[2];
	float KneelLeg[2];
	float Stride[2] = {0.0f, 0.0f};
	float SwaySum = 0.0f, SwayWeight = 0.0f;
	for (int32 s = 0; s < 2; ++s)
	{
		const FFoot& F = G.Feet[s];
		FVector P = G.bFeetKnown ? ToWorld.InverseTransformPosition(FVector(F.Pos.X, F.Pos.Y, G.Position.Z))
			: FVector(s == 0 ? R.HipX * StanceWidth : -R.HipX * StanceWidth, 0.0, 0.0);
		Stride[s] = float(P.Y);
		// a foot left behind rolls onto its toes; one in the air is lifted
		const float Heel = P.Y < 0.0 ? FMath::Min(6.0f, -0.25f * float(P.Y)) : 0.0f;
		const float Z = R.AnkleZ + F.Lift / B.Height + Heel;
		const float W = 1.0f - 0.9f * F.Lift / (StepLift * B.Height);
		SwaySum += W * float(P.X);
		SwayWeight += W;
		KneelLeg[s] = s == 1 ? FMath::SmoothStep(0.0f, 0.75f, K) : FMath::SmoothStep(0.25f, 1.0f, K);
		const float Slide = FMath::Sin(PI * KneelLeg[s]);
		P.Y -= R.KneelBack * KneelLeg[s];
		P.Z = FMath::Lerp(Z, 6.0f, KneelLeg[s]) + 3.0f * Slide * Slide;
		Ankle[s] = P;
	}

	TArray<FQuat> D;
	D.Init(FQuat::Identity, N);
	TArray<FVector> Shift;
	Shift.Init(FVector::ZeroVector, N);
	// the pelvis: down onto the knees; standing, a little lower the further apart the feet are (lowest
	// when both are on the ground a step apart, highest as one passes the other), and a shade towards
	// the foot that carries the weight
	const float Spread = FMath::Min(FMath::Abs(Stride[0] - Stride[1]) / StepLength, 1.3f);
	Shift[R.Pelvis] = FVector(0.25 * (1.0 - K) * SwaySum / FMath::Max(SwayWeight, 0.1f), 0.0,
		-R.KneelDrop * K - (1.0f - K) * (1.0f + 3.0f * Spread * Spread));
	const float SpineBow[5] = {-5.0f, -7.0f, -7.0f, -5.0f, -4.0f};
	for (int32 k = 0; k < 5; ++k)
	{
		D[R.Spine[k]] = AboutX(SpineBow[k] * SpineW + (k == 0 ? -4.0f * K : 0.0f) + (k == 4 ? 4.0f * O : 0.0f));
	}
	D[R.Neck] = AboutX(-10.0f * HeadW);
	D[R.Head] = AboutX(-14.0f * HeadW + 14.0f * O);
	TArray<FTransform>& CS = G.CS;
	CS.SetNum(N);
	for (int32 i = 0; i < N; ++i)
	{
		const int32 P = Ref.GetParentIndex(i);
		FTransform L = Local[i];
		if (!D[i].Equals(FQuat::Identity, 1e-5f) || !Shift[i].IsNearlyZero())
		{
			const FQuat PR = P >= 0 ? CS[P].GetRotation() : FQuat::Identity;
			L.SetRotation((PR.Inverse() * D[i] * PR * L.GetRotation()).GetNormalized());
			L.AddToTranslation(PR.Inverse().RotateVector(Shift[i]));
		}
		CS[i] = P >= 0 ? L * CS[P] : L;
	}

	// the legs: knee from hip and ankle, bending forwards; the foot flat on the floor, or stretched
	// out behind when kneeling
	for (int32 s = 0; s < 2; ++s)
	{
		const FVector Hip = CS[R.Thigh[s]].GetLocation();
		FVector A = Ankle[s];
		const FVector Knee = SolveElbow(Hip, A, R.ThighLength, R.CalfLength, FVector(s == 0 ? 0.12 : -0.12, 1.0, 0.0));
		const float Toed = FMath::DegreesToRadians(FMath::FindDeltaAngleDegrees(G.Yaw, G.Feet[s].Yaw));
		const FVector Along(-FMath::Sin(Toed), FMath::Cos(Toed), 0.0);
		const float Flat = FMath::Asin(FMath::Clamp((R.AnkleZ - R.BallZ) / FMath::Max(R.FootLength, 1.0f), 0.0f, 1.0f));
		const float Tilt = FMath::Lerp(Flat, PI - 0.35f, KneelLeg[s]);
		FVector Toe = A + Along * (R.FootLength * FMath::Cos(Tilt)) - FVector(0.0, 0.0, R.FootLength * FMath::Sin(Tilt));
		Toe.Z = FMath::Max(Toe.Z, 1.5);
		CS[R.Calf[s]].SetLocation(Knee);
		CS[R.Foot[s]].SetLocation(A);
		CS[R.Ball[s]].SetLocation(Toe);
	}
}

void AF3GhostDriver::BuildBody(const FGhost& G, TArray<FPrim>& Out) const
{
	if (G.CS.Num() == 0)
	{
		return;
	}
	const FBuildDef& B = Builds[G.Build];
	const FRig& R = Rig;
	const float Gi = B.Girth;
	const float Li = FMath::Sqrt(Gi);   // limbs thicken less than the trunk
	const FVector Left(1.0, 0.0, 0.0), Fwd(0.0, 1.0, 0.0), Up(0.0, 0.0, 1.0);
	auto J = [&G](int32 Bone) { return G.CS[Bone].GetLocation(); };
	const int32 First = Out.Num();
	auto Add = [&Out](const FVector& A, const FVector& End, float RA, float RB)
	{
		FPrim P;
		P.A = A;
		P.B = End;
		P.RA = RA;
		P.RB = RB;
		P.Strength = 1.0f;
		P.Kind = 0.0f;
		P.Pad = BodyPad;
		P.Noise = 0.0f;
		Out.Add(P);
	};

	const bool bToga = B.Garb == EGarb::Toga;
	const bool bLong = B.Garb != EGarb::Tunic;

	// the joints, in the figure's own space (mannequin size; scaled to the build at the end)
	const FVector Pelvis = J(R.Pelvis);
	const FVector Waist = J(R.Spine[1]);
	const FVector Chest = J(R.Spine[3]);
	const FVector Neck = J(R.Neck);
	const FQuat HeadRot = G.CS[R.Head].GetRotation();
	const FVector HeadUp = HeadRot.RotateVector(R.HeadUpLocal);
	const FVector HeadFwd = HeadRot.RotateVector(R.HeadForwardLocal);
	const FVector Head = J(R.Head) + HeadUp * 9.0;
	const FVector SpineDir = (Chest - Pelvis).GetSafeNormal();
	const FVector TorsoFwd = FVector::CrossProduct(SpineDir, Left).GetSafeNormal();
	FVector Sh[2] = {J(R.UpperArm[0]), J(R.UpperArm[1])};
	const FVector ShMid = 0.5 * (Sh[0] + Sh[1]);
	FVector Hip[2], Knee[2], Ankle[2], Toe[2];
	for (int32 s = 0; s < 2; ++s)
	{
		Sh[s] = ShMid + (Sh[s] - ShMid) * B.Shoulders;
		Hip[s] = J(R.Thigh[s]);
		Knee[s] = J(R.Calf[s]);
		Ankle[s] = J(R.Foot[s]);
		Toe[s] = J(R.Ball[s]);
	}

	// The arms, by IK. Hands clasped before the body while standing and walking (user, 2026-11-23),
	// joined in prayer at the breast while kneeling, raised and apart for the priest's prayer.
	const float K = G.Kneel.Value;
	const float O = G.Orans.Value;
	const float Front = (B.bFemale ? 13.0f : 15.5f) * Gi + 6.0f;
	const FVector Clasp = FMath::Lerp(Pelvis, Chest, 0.42f) + TorsoFwd * Front;
	const FVector Pray = FMath::Lerp(Pelvis, Chest, 0.95f) + TorsoFwd * (Front + 2.0f);
	const FVector Low = FMath::Lerp(Clasp, Pray, K);
	FVector Elbow[2], Hand[2];
	for (int32 s = 0; s < 2; ++s)
	{
		const FVector Side = s == 0 ? Left : -Left;
		const FVector Raised = Sh[s] + Up * 17.0 + Side * 27.0 + Fwd * 22.0;   // hands at the height of the ears, apart, palms forward
		Hand[s] = FMath::Lerp(Low + Side * 2.5, Raised, O);
		// the elbows hang by the body, a little back, not out to the sides (user, 2026-11-23: puffy
		// elbows); only the raised arms open outwards
		const FVector Pole = Side * FMath::Lerp(0.3f, 1.0f, O) - Up - Fwd * 0.5;
		Elbow[s] = SolveElbow(Sh[s], Hand[s], R.UpperArmLength, R.ForeArmLength, Pole);
	}

	// head and trunk (the head first: the trail takes its top from it)
	Add(Head, Head, 10.3f, 10.3f);
	Add(Neck, Head - HeadUp * 4.0, 6.3f * Li, 6.5f * Li);
	if (B.bFemale)
	{
		// Narrow shoulders and a smaller waist, but a full chest: with the mannequin's wide shoulder
		// joints a slight trunk left the shoulders and arms standing out like a skeleton's (user,
		// 2026-11-23). The wrap also fills each side from under the shoulder down to the hip, so the
		// arms lie against the body.
		Add(FMath::Lerp(Sh[0], ShMid, 0.2f), FMath::Lerp(Sh[1], ShMid, 0.2f), 7.5f * Gi, 7.5f * Gi);
		Add(ShMid - Up * 3.0, Chest, 13.5f * Gi, 15.0f * Gi);
		Add(Chest, Waist, 15.0f * Gi, 13.0f * Gi);
		Add(Waist, Pelvis, 13.0f * Gi, 14.5f * Gi);
		for (int32 s = 0; s < 2; ++s)
		{
			Add(FMath::Lerp(Sh[s], ShMid, 0.25f) - Up * 6.0, FMath::Lerp(Hip[s], Sh[s], 0.12f), 8.5f * Gi, 9.5f * Gi);
		}
	}
	else
	{
		Add(FMath::Lerp(Sh[0], ShMid, 0.2f), FMath::Lerp(Sh[1], ShMid, 0.2f), 7.5f * Gi, 7.5f * Gi);
		Add(ShMid - Up * 3.0, Chest, 13.0f * Gi, 16.0f * Gi);
		Add(Chest, Waist, 16.0f * Gi, 14.5f * Gi);
		Add(Waist, Pelvis, 14.5f * Gi, 15.5f * Gi);
	}

	// arms, and the drape
	for (int32 s = 0; s < 2; ++s)
	{
		// the left arm of a toga is wrapped in it; every other arm is in a plain sleeve or bare
		const bool bWrapped = bToga && s == 0;
		const float Arm = (bWrapped ? 1.2f : 1.0f) * Li;
		Add(Sh[s], Elbow[s], 5.6f * Arm, 4.7f * Arm);
		Add(Elbow[s], Hand[s], 4.7f * Arm, 3.9f * Arm);
		Add(Hand[s], Hand[s], 4.4f, 4.4f);
	}
	if (bLong)
	{
		// from the left shoulder across the chest to the right hip, and down the back
		const float Drape = bToga ? 1.0f : 0.8f;
		const FVector On = FMath::Lerp(Sh[0], ShMid, 0.35f) + Up * 1.0;   // where it lies on the shoulder: thin there
		Add(On, Hip[1] + TorsoFwd * 7.0, 5.0f * Gi * Drape, 7.0f * Gi * Drape);
		Add(On, Pelvis - TorsoFwd * 9.0 + Left * 6.0, 5.0f * Gi * Drape, 7.0f * Gi * Drape);
	}
	if (G.bPriest)
	{
		// the priest's toga drawn over his head, as at a sacrifice (capite velato; user, 2026-11-23):
		// close round the head and down onto the shoulders, not a deep hood
		const FVector Crown = Head - HeadFwd * 1.5;
		Add(Crown, Crown, 11.6f, 11.6f);
		Add(Crown, ShMid - TorsoFwd * 5.0, 11.2f, 12.0f * Gi);
	}

	// Below the waist: one garment, not two trouser legs. A leg that swings forward pulls the cloth
	// with it (user, 2026-11-23: the legs went beyond the fabric): besides the cloth over each leg
	// there is cloth stretched from knee to knee and from hem to hem, and the middle is filled. The
	// feet stay under a long garment.
	if (bLong)
	{
		FVector Hem[2];
		for (int32 s = 0; s < 2; ++s)
		{
			Hem[s] = Ankle[s];
			Hem[s].Z = FMath::Max(Ankle[s].Z - 2.0, 3.0);
			Add(Hip[s], Knee[s], 12.0f * Gi, 11.5f * Gi);
			Add(Knee[s], Hem[s], 11.5f * Gi, 11.5f * Gi);
		}
		Add(Knee[0], Knee[1], 11.5f * Gi, 11.5f * Gi);
		Add(Hem[0], Hem[1], 11.5f * Gi, 11.5f * Gi);
		Add(Pelvis, 0.5 * (Hem[0] + Hem[1]), 14.0f * Gi, 11.5f * Gi);
	}
	else
	{
		for (int32 s = 0; s < 2; ++s)
		{
			Add(Hip[s], Knee[s], 12.5f * Gi, 12.0f * Gi);
			Add(Knee[s], Ankle[s], 6.5f * Li, 4.8f * Li);
			Add(Ankle[s], Toe[s], 5.0f, 4.3f);
		}
		Add(Knee[0], Knee[1], 12.0f * Gi, 12.0f * Gi);
		Add(Pelvis, 0.5 * (Knee[0] + Knee[1]), 14.5f * Gi, 12.0f * Gi);
	}

	// to the world, at the build's height (the mannequin faces +Y)
	const FTransform ToWorld(FRotator(0.0, G.Yaw - 90.0, 0.0), G.Position, FVector(B.Height));
	G.TraceHand[0] = ToWorld.TransformPosition(Hand[0]);
	G.TraceHand[1] = ToWorld.TransformPosition(Hand[1]);
	G.TracePelvis = ToWorld.TransformPosition(Pelvis);
	for (int32 i = First; i < Out.Num(); ++i)
	{
		FPrim& P = Out[i];
		P.A = ToWorld.TransformPosition(P.A);
		P.B = ToWorld.TransformPosition(P.B);
		P.RA *= B.Height;
		P.RB *= B.Height;
	}
}

void AF3GhostDriver::BuildTrail(FGhost& G, float Time, const FVector& Head, TArray<FPrim>& Out) const
{
	// The trail: every TrailInterval the figure leaves a puff where it stands, from the floor to its
	// head. A puff drifts on the wind, widens and fades over TrailSeconds; one left while walking is
	// stronger than one left while kneeling, so a still figure only steams a little. The material
	// joins each puff to the next into one ribbon, which starts at the figure itself.
	const FBuildDef& B = Builds[G.Build];
	const float Scale = B.Height * B.Girth;
	const float Moving = FMath::Lerp(0.25f, 1.0f, FMath::Clamp(G.Speed / 30.0f, 0.0f, 1.0f));
	if (Time - G.LastPuff >= TrailInterval)
	{
		FPuff P;
		P.Time = Time;
		P.Base = G.Position;
		P.Top = Head;
		P.Scale = Scale;
		P.Strength = Moving;
		G.Trail.Add(P);
		G.LastPuff = Time;
	}
	G.Trail.RemoveAll([&](const FPuff& P) { return Time - P.Time > TrailSeconds; });
	const int32 First = Out.Num();
	auto Add = [&](const FVector& Base, const FVector& Top, float PuffScale, float Strength, float Age)
	{
		const float Life = FMath::Clamp(Age / TrailSeconds, 0.0f, 1.0f);
		const float Grow = 1.0f + TrailGrowth * Life;
		FPrim T;
		T.A = Base + FVector(0.0, 0.0, 24.0 * PuffScale) + Wind * Age;
		T.B = Top + Wind * (Age * 1.2f);
		T.RA = 22.0f * PuffScale * Grow;
		T.RB = 14.0f * PuffScale * Grow;
		T.Strength = TrailStrength * Strength * FMath::Pow(1.0f - Life, 1.4f);
		T.Kind = 1.0f;
		T.Noise = 8.0f + 22.0f * Life;
		T.Pad = T.Noise;
		Out.Add(T);
	};
	Add(G.Position, Head, Scale, Moving, 0.0f);
	for (int32 i = G.Trail.Num() - 1; i >= 0; --i)
	{
		const FPuff& P = G.Trail[i];
		Add(P.Base, P.Top, P.Scale, P.Strength, Time - P.Time);
	}
	if (Out.Num() > First)
	{
		Out.Last().Kind = 2.0f;   // the ribbon ends here
	}
}

void AF3GhostDriver::PlaceQuad(FGhost& G, const TArray<FPrim>& Prims, bool bCamera, const FVector& Camera, const FVector& CameraForward) const
{
	AStaticMeshActor* Quad = G.Quad.Get();
	UMaterialInstanceDynamic* Mist = G.Mist.Get();
	if (!Quad || !Mist)
	{
		return;
	}
	// a sphere round everything the ghost is made of
	FBox Box(ForceInit);
	for (const FPrim& P : Prims)
	{
		Box += P.A;
		Box += P.B;
	}
	const FVector Centre = Prims.Num() ? Box.GetCenter() : G.Position;
	float Radius = 10.0f;
	for (const FPrim& P : Prims)
	{
		Radius = FMath::Max3(Radius, float(FVector::Dist(Centre, P.A)) + P.RA + P.Pad, float(FVector::Dist(Centre, P.B)) + P.RB + P.Pad);
	}
	// The quad stands on the near side of that sphere, facing the camera: every ray into the sphere
	// crosses it first, so the depth test against the building stays right. When the camera is in or
	// almost in the sphere, it stands just in front of the camera and covers the view.
	FVector Location = Centre;
	FVector Normal = FVector::UpVector;
	float Half = Radius * 1.2f;
	if (bCamera)
	{
		const FVector To = Camera - Centre;
		const float Dist = To.Size();
		if (Dist > Radius + 40.0f)
		{
			Normal = To / Dist;
			Location = Centre + Normal * Radius;
		}
		else
		{
			Normal = -CameraForward;
			Location = Camera + CameraForward * 20.0;
			Half = 150.0f;
		}
	}
	Quad->SetActorLocationAndRotation(Location, FRotationMatrix::MakeFromZ(Normal).Rotator());
	Quad->SetActorScale3D(FVector(Half / 50.0f));   // the engine's plane is 100 cm across
	const FVector Origin = Quad->GetStaticMeshComponent()->Bounds.Origin;   // what the material's object position is
	Mist->SetVectorParameterValue(TEXT("QuadPos"), FLinearColor(float(Origin.X), float(Origin.Y), float(Origin.Z), 0.0f));
	Mist->SetVectorParameterValue(TEXT("Bound"), FLinearColor(float(Centre.X), float(Centre.Y), float(Centre.Z), Radius));
	Mist->SetVectorParameterValue(TEXT("Anchor"), FLinearColor(float(G.Position.X), float(G.Position.Y), float(G.Position.Z), FMath::DegreesToRadians(G.Yaw)));
	Mist->SetScalarParameterValue(TEXT("Count"), float(Prims.Num()));
}

void AF3GhostDriver::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bReady || !PrimTexture)
	{
		return;
	}
	const float Time = GetWorld()->GetTimeSeconds();
	const float Dt = LastTime < 0.0f ? 0.0f : FMath::Clamp(Time - LastTime, 0.0f, 0.1f);
	LastTime = Time;

	bool bCamera = false;
	FVector Camera = FVector::ZeroVector;
	FVector CameraForward = FVector::ForwardVector;
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (PC->PlayerCameraManager)
		{
			Camera = PC->PlayerCameraManager->GetCameraLocation();
			CameraForward = PC->PlayerCameraManager->GetCameraRotation().Vector();
			bCamera = true;
		}
	}

	// three rows of capsules per ghost: A and radius, B and radius, strength / kind / pad / noise
	TArray<FLinearColor> Data;
	Data.SetNumZeroed(MaxPrims * 3 * NumGhosts);
	TArray<FPrim> Prims;
	for (int32 g = 0; g < Ghosts.Num(); ++g)
	{
		FGhost& G = Ghosts[g];
		StepGhost(G, Dt);
		Prims.Reset();
		BuildBody(G, Prims);
		BuildTrail(G, Time, Prims.Num() ? Prims[0].A : G.Position + FVector(0.0, 0.0, 150.0), Prims);
		if (Prims.Num() > MaxPrims)
		{
			Prims.SetNum(MaxPrims);
		}
		PlaceQuad(G, Prims, bCamera, Camera, CameraForward);
		if (!TraceFile.IsEmpty() && Prims.Num() > 0)
		{
			const FVector H = Prims[0].A;
			TraceLines.Add(FString::Printf(TEXT("%.4f,%d,%d,%.3f,%.3f,%.3f,%.3f,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f"),
				Time, g, int32(G.State), G.Position.X, G.Position.Y, G.Yaw, G.Speed, G.Kneel.Value, G.Bow.Value, G.Orans.Value, H.X, H.Y, H.Z, G.TracePelvis.Z,
				G.Feet[0].Pos.X, G.Feet[0].Pos.Y, G.Feet[0].Lift, G.Feet[1].Pos.X, G.Feet[1].Pos.Y, G.Feet[1].Lift,
				G.TraceHand[0].X, G.TraceHand[0].Y, G.TraceHand[0].Z, G.TraceHand[1].X, G.TraceHand[1].Y, G.TraceHand[1].Z));
		}
		for (int32 i = 0; i < Prims.Num(); ++i)
		{
			const FPrim& P = Prims[i];
			Data[(g * 3) * MaxPrims + i] = FLinearColor(float(P.A.X), float(P.A.Y), float(P.A.Z), P.RA);
			Data[(g * 3 + 1) * MaxPrims + i] = FLinearColor(float(P.B.X), float(P.B.Y), float(P.B.Z), P.RB);
			Data[(g * 3 + 2) * MaxPrims + i] = FLinearColor(P.Strength, P.Kind, P.Pad, P.Noise);
		}
	}
	// write the mip and rebuild the resource: reliable for a texture this small (UpdateTextureRegions
	// on a transient float texture did not reach the shader)
	FTexture2DMipMap& Mip = PrimTexture->GetPlatformData()->Mips[0];
	void* Dest = Mip.BulkData.Lock(LOCK_READ_WRITE);
	FMemory::Memcpy(Dest, Data.GetData(), Data.Num() * sizeof(FLinearColor));
	Mip.BulkData.Unlock();
	PrimTexture->UpdateResource();

	if (TraceLines.Num() >= 600)
	{
		FlushTrace();
	}
	if (++LogCounter % 240 == 1)
	{
		FString States;
		for (const FGhost& G : Ghosts)
		{
			States += FString::Printf(TEXT(" [%s st%d s%d k%.2f b%.2f o%.2f v%.0f at %.0f,%.0f]"), G.bPriest ? TEXT("priest") : TEXT("w"),
				int32(G.State), G.Station, G.Kneel.Value, G.Bow.Value, G.Orans.Value, G.Speed, G.Position.X, G.Position.Y);
		}
		UE_LOG(LogTemp, Display, TEXT("F3GhostDriver: t %.1f%s"), Time, *States);
	}
}

void AF3GhostDriver::FlushTrace()
{
	if (!TraceFile.IsEmpty() && TraceLines.Num() > 0)
	{
		FFileHelper::SaveStringToFile(FString::Join(TraceLines, TEXT("\n")) + TEXT("\n"), *TraceFile, FFileHelper::EEncodingOptions::AutoDetect,
			&IFileManager::Get(), FILEWRITE_Append);
		TraceLines.Reset();
	}
}
