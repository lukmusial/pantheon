// Game mode of the walk-through app (F2): spawns the visitor in the forecourt, adds the help overlay.
// Film renders are unaffected: Movie Render Queue runs with its own game mode.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "PantheonGameMode.generated.h"

UCLASS()
class PANTHEON_API APantheonGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	APantheonGameMode();

	virtual void RestartPlayer(AController* NewPlayer) override;

protected:
	virtual void BeginPlay() override;
};
