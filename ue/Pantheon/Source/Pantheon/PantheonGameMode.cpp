#include "PantheonGameMode.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "PantheonHUD.h"
#include "PantheonVisitor.h"

APantheonGameMode::APantheonGameMode()
{
	DefaultPawnClass = APantheonVisitor::StaticClass();
	HUDClass = APantheonHUD::StaticClass();
}

void APantheonGameMode::RestartPlayer(AController* NewPlayer)
{
	// the level has no PlayerStart; the visitor starts in the forecourt facing the portico
	RestartPlayerAtTransform(NewPlayer, APantheonVisitor::StartTransform());
}

void APantheonGameMode::BeginPlay()
{
	Super::BeginPlay();
	// Flame and smoke cards are engine planes with simple box collision: the visitor would bump into
	// invisible walls at every brazier, so they stop colliding (the braziers themselves still do).
	int32 Cards = 0;
	for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
	{
		UStaticMeshComponent* Mesh = It->GetStaticMeshComponent();
		if (Mesh && Mesh->GetStaticMesh() && Mesh->GetStaticMesh()->GetPathName().StartsWith(TEXT("/Engine/BasicShapes/Plane")))
		{
			Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			++Cards;
		}
	}
	UE_LOG(LogTemp, Log, TEXT("Pantheon: collision off on %d flame and smoke cards"), Cards);

	// The sun's shadows are ray traced in the walk-through. With virtual shadow maps its shadow edge
	// on the portico shafts came out as a coarse sawtooth whatever the resolution, page pool or bias;
	// cascaded shadow maps were clean but halved the frame rate (every fire light then renders cube
	// shadow maps of the Nanite statues). Only the sun changes: the fires keep virtual shadow maps,
	// and the films (Movie Render Queue, own game mode) are unaffected (user, 2026-11-23).
	for (TActorIterator<ADirectionalLight> It(GetWorld()); It; ++It)
	{
		if (UDirectionalLightComponent* Sun = Cast<UDirectionalLightComponent>(It->GetLightComponent()))
		{
			Sun->CastRaytracedShadow = ECastRayTracedShadow::Enabled;
			Sun->MarkRenderStateDirty();
		}
	}
}
