package types

import (
	"fmt"
	"strings"
)

// BuildClassID namespaces classes under the creator address.
// Format: nft/<creator>/<subID>
func BuildClassID(creator, subID string) (string, error) {
	sub := strings.TrimSpace(subID)
	if sub == "" {
		return "", ErrInvalidSubID
	}
	if strings.Contains(sub, "/") {
		return "", ErrInvalidSubID
	}
	c := strings.TrimSpace(creator)
	if c == "" {
		return "", ErrInvalidSubID
	}
	return fmt.Sprintf("nft/%s/%s", c, sub), nil
}
